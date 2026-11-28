"""Transactional portal email outbox and bounded delivery worker."""
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import uuid4

from flask import current_app
from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from medical_services import TZ
from delivery_limits import reserve
from mail_delivery import DeliveryFailure
from models import AccountVerification, DeliveryLimit, EmailDeliveryRun, SecurityEmail, User
from portal_sessions import clock

ACCOUNT_EMAIL_KINDS = frozenset({'verify', 'welcome', 'login', 'change'})

@dataclass(frozen=True)
class Message:
    recipient: str
    subject: str
    body: str
    idempotency_key: str


class FakeMailProvider:
    live = False

    def __init__(self):
        self.messages = {}

    def send(self, message):
        self.messages.setdefault(message.idempotency_key, message)


def trusted_origin(value, *, https_only=False):
    parsed = urlsplit(value)
    port = parsed.port
    if (parsed.scheme not in (('https',) if https_only else ('http', 'https')) or
            not parsed.hostname or parsed.username is not None or '?' in value or '#' in value or
            port == 0 or parsed.path not in ('', '/') or
            any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value) or '\\' in value):
        raise ValueError('Expected a trusted portal origin.')
    return value.rstrip('/')


def enqueue(user, kind, key, *, detail=None, recipient=None):
    if kind not in ACCOUNT_EMAIL_KINDS:
        raise ValueError('Unsupported account email purpose.')
    now = clock()
    db.session.add(SecurityEmail(dedupe_key=key, user_id=user.id, recipient=recipient or user.email,
        kind=kind, detail=detail, created_at=now, next_attempt_at=now))


def render(job):
    from account_verification import verification_token
    from appointment_email import SUBJECTS, render as render_appointment

    if job.kind not in ACCOUNT_EMAIL_KINDS and job.kind not in SUBJECTS:
        return None
    origin = trusted_origin(current_app.config['AUTH_PUBLIC_URL'],
                            https_only=current_app.config['PRODUCTION'])
    support = origin + '/auth/help'
    if job.kind in SUBJECTS:
        rendered = render_appointment(job, origin)
        return Message(job.recipient, *rendered, job.dedupe_key) if rendered else None
    user = db.session.execute(select(User.email, User.enabled).where(User.id == job.user_id)).first()
    if not user or (not user.enabled and job.kind != 'change'):
        return None
    if job.kind in ('welcome', 'login') and user.email != job.recipient:
        return None
    if job.kind == 'verify':
        state = db.session.execute(select(AccountVerification.verification_id, AccountVerification.requested_email,
            AccountVerification.expires_at).where(AccountVerification.user_id == job.user_id)).first()
        if (not state or state.verification_id != job.detail or
                state.requested_email != job.recipient or state.expires_at <= clock()):
            return None
        token = verification_token(state.verification_id, job.user_id, job.recipient)
        subject = 'Confirm your Ramosolo email address'
        body = f'Open this link and choose Confirm email to verify your address.\n{origin}/auth/verify?t={token}'
    elif job.kind == 'welcome':
        subject = 'Welcome to the Ramosolo portal'
        body = (f'Sign in at {origin}/auth/login. Follow the on-screen prompts to set up your authenticator '
                'if requested, and store any recovery codes securely.')
    elif job.kind == 'login':
        utc = datetime.fromtimestamp(job.created_at, timezone.utc)
        local = utc.astimezone(TZ)
        subject = 'Ramosolo portal sign-in'
        body = (f'Sign-in completed at {utc:%Y-%m-%d %H:%M:%S} UTC '
                f'({local:%Y-%m-%d %H:%M:%S %Z}, Africa/Johannesburg).\n'
                f'Approximate device: {job.detail}.')
    elif job.kind == 'change':
        subject = 'Ramosolo account security change'
        body = f'Your Ramosolo account security settings changed. {job.detail}'
    else:
        return None
    return Message(job.recipient, subject,
                   f'{body}\n\nFor help or if this was unexpected, visit {support}.',
                   job.dedupe_key)


def finish_failure(job, failure):
    now = clock()
    delay = max(failure.retry_after, 60 * 2 ** (min(job.attempts, 5) - 1))
    if failure.outcome == 'hold':
        job.attempts -= 1
        job.state = 'pending'
    elif failure.outcome in ('retry', 'quota') and job.attempts < 5:
        job.state = 'pending'
    else:
        job.state = 'uncertain' if failure.outcome == 'uncertain' else 'failed'
    job.next_attempt_at = now + delay
    job.result_code = {'hold': 'pilot_hold', 'retry': 'provider_retry', 'quota': 'provider_quota',
                       'uncertain': 'outcome_unknown', 'failed': 'provider_rejected'}.get(
                           failure.outcome, 'provider_failed')
    if failure.outcome == 'quota':
        from sqlalchemy.dialects.postgresql import insert as postgres_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        insert = postgres_insert if db.session.get_bind().dialect.name == 'postgresql' else sqlite_insert
        block = insert(DeliveryLimit).values(key='gmail:pause', expires_at=now + delay, count=1)
        db.session.execute(block.on_conflict_do_update(index_elements=[DeliveryLimit.key],
            set_={'expires_at': now + delay}, where=DeliveryLimit.expires_at < now + delay))
    current_app.logger.warning('Outbound email state=%s attempt=%d', job.state, job.attempts)


def recover_interrupted(now):
    # Skip an active worker that still holds a row lock, even after a hard lease timeout.
    stale_jobs = select(SecurityEmail.dedupe_key).where(SecurityEmail.state == 'sending',
        SecurityEmail.next_attempt_at <= now).with_for_update(skip_locked=True)
    db.session.execute(update(SecurityEmail).where(SecurityEmail.dedupe_key.in_(stale_jobs))
                       .values(state='uncertain', result_code='worker_lease_expired'))
    stale_runs = select(EmailDeliveryRun.id).where(EmailDeliveryRun.state == 'running',
        EmailDeliveryRun.lease_until <= now).with_for_update(skip_locked=True)
    db.session.execute(update(EmailDeliveryRun).where(EmailDeliveryRun.id.in_(stale_runs))
                       .values(state='interrupted', finished_at=now))


def bump(run, event):
    run.counts = {**run.counts, event: run.counts.get(event, 0) + 1}
    run.lease_until = clock() + 300


def dispatch(provider, run, limit, live):
    for _ in range(limit):
        now = clock()
        if live:
            pause = db.session.get(DeliveryLimit, 'gmail:pause')
            if pause and pause.expires_at > now:
                db.session.rollback()
                break
        due = select(SecurityEmail).where(SecurityEmail.state == 'pending', SecurityEmail.next_attempt_at <= now)
        if live:
            due = due.where(func.lower(SecurityEmail.recipient).in_(provider.recipients))
        job = db.session.scalar(due.order_by(SecurityEmail.next_attempt_at, SecurityEmail.dedupe_key)
                                .limit(1).with_for_update(skip_locked=True))
        if job is None:
            db.session.rollback()
            break
        key = job.dedupe_key
        if live and not provider.accepts(job.recipient):
            job.next_attempt_at = now + 3600
            db.session.commit()
            continue
        if live and not reserve(now, ('gmail:daily', 86400, provider.daily_limit)):
            db.session.rollback()
            break
        changed = db.session.execute(update(SecurityEmail).where(SecurityEmail.dedupe_key == key,
            SecurityEmail.state == 'pending', SecurityEmail.next_attempt_at <= now).values(
            state='sending', attempts=SecurityEmail.attempts + 1, next_attempt_at=now + 120,
            last_run_id=run.id, result_code=None)).rowcount
        if changed == 1:
            bump(run, 'claimed')
        db.session.commit()
        if changed != 1:
            continue
        job = db.session.get(SecurityEmail, key, with_for_update=True, populate_existing=True)
        if not job or job.last_run_id != run.id or job.state != 'sending' or job.next_attempt_at <= clock():
            db.session.rollback()
            continue
        db.session.refresh(run, with_for_update=True)
        if run.state != 'running':
            db.session.rollback()
            break
        message = None
        try:
            message = render(job)
            if message is None:
                job.state = 'cancelled'
                job.result_code = 'ineligible_or_stale'
            else:
                provider.send(message)
                job.state = 'accepted' if live else 'simulated'
                job.result_code = 'provider_accepted' if live else 'fake_processed'
        except DeliveryFailure as failure:
            finish_failure(job, failure)
        except SQLAlchemyError:
            raise
        except Exception:
            if message is None:
                job.state = 'failed'
                job.result_code = 'render_failed'
            else:
                finish_failure(job, DeliveryFailure('unexpected_worker_failure',
                    outcome='uncertain' if live else 'retry'))
        bump(run, job.state)
        db.session.commit()


def deliver_with_run(provider, *, limit=25):
    """Persist run statistics and commit an individual claim before any external send."""
    live = getattr(provider, 'live', False)
    now = clock()
    recover_interrupted(now)
    run = EmailDeliveryRun(id=uuid4().hex, mode='live' if live else 'fake', state='running',
                           started_at=now, lease_until=now + 300, counts={})
    db.session.add(run)
    db.session.commit()
    try:
        dispatch(provider, run, limit, live)
    except Exception:
        db.session.rollback()
        finalize_run(run, 'failed')
        raise
    finalize_run(run, 'completed')
    return run


def finalize_run(run, state):
    db.session.execute(update(EmailDeliveryRun).where(EmailDeliveryRun.id == run.id,
        EmailDeliveryRun.state == 'running').values(state=state, finished_at=clock()))
    db.session.commit()


def deliver_pending(provider, *, limit=25):
    report = deliver_with_run(provider, limit=limit)
    return report.counts.get('accepted', 0) + report.counts.get('simulated', 0)
