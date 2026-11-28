import base64
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from unittest.mock import MagicMock

import pyotp
import pytest
import requests
from cryptography.fernet import Fernet
from sqlalchemy import select

import appointment_email
import multi_factor
import phone_verification
import portal_sessions
import security_email
from extensions import db
from mail_delivery import DeliveryFailure, GMAIL_FROM, GMAIL_SCOPE, SEND_URL, TOKEN_URL, GmailProvider
from models import (Appointment, AppointmentEmail, Authenticator, CommunicationDecision, EmailDeliveryRun, PhoneChallenge,
                    SecurityEmail, VerifiedPhone)
from sms_delivery import FakeSMSProvider, ProviderUnavailable, TwilioVerifyProvider
from test_account_security import copy_cookie, password_login
from test_calendar import approved, local, time as wall_time, utc_on
from test_medical import as_user, env


def response(status, payload, headers=None):
    result = MagicMock(status_code=status, headers=headers or {})
    result.json.return_value = payload
    return result


def test_worker_recovers_committed_claim_without_duplicate_send(env, monkeypatch):
    now = 1_800_000_000
    monkeypatch.setattr(security_email, 'clock', lambda: now)
    previous = EmailDeliveryRun(id='previous-synthetic-run', mode='fake', state='running',
        started_at=now - 300, lease_until=now, counts={'claimed': 1})
    db.session.add(previous)
    security_email.enqueue(env[1]['patient'], 'change', 'synthetic-abandoned', detail='Synthetic change')
    security_email.enqueue(env[1]['patient'], 'change', 'synthetic-new', detail='Synthetic change')
    db.session.flush()
    abandoned = db.session.get(SecurityEmail, 'synthetic-abandoned')
    abandoned.state, abandoned.last_run_id, abandoned.attempts = 'sending', previous.id, 1
    db.session.commit()

    provider = security_email.FakeMailProvider()
    report = security_email.deliver_with_run(provider)
    assert report.state == 'completed' and report.finished_at == now
    assert report.counts == {'claimed': 1, 'simulated': 1}
    assert list(provider.messages) == ['synthetic-new']
    assert abandoned.state == 'uncertain' and abandoned.result_code == 'worker_lease_expired'
    assert previous.state == 'interrupted' and previous.finished_at == now
    delivered = db.session.get(SecurityEmail, 'synthetic-new')
    assert (delivered.last_run_id, delivered.result_code) == (report.id, 'fake_processed')


def test_gmail_oauth_only_sends_from_confirmed_mailbox_to_one_recipient(env):
    http = MagicMock()
    http.post.side_effect = [response(200, {'access_token': 'synthetic-access', 'scope': GMAIL_SCOPE}),
                             response(200, {'id': 'synthetic-accepted'})]
    config = env[0].config
    config.update(MAIL_PROVIDER='gmail-oauth', MAIL_LIVE_ENABLED=True, GMAIL_DAILY_LIMIT=2,
        MAIL_PILOT_RECIPIENTS='pilot@example.test', MAIL_DISPLAY_NAME='Synthetic portal',
        MAIL_REPLY_TO='reply@example.test', GMAIL_OAUTH_CLIENT_ID='synthetic-id',
        GMAIL_OAUTH_CLIENT_SECRET='synthetic-secret', GMAIL_OAUTH_REFRESH_TOKEN='synthetic-refresh')
    adapter = GmailProvider(config, http=http)
    msg = security_email.Message('pilot@example.test', 'An appointment update', 'Minimal body', 'synthetic-1')
    adapter.send(msg)
    auth, sent = http.post.call_args_list
    assert auth.args == (TOKEN_URL,) and auth.kwargs['data']['grant_type'] == 'refresh_token'
    assert sent.args == (SEND_URL,) and GMAIL_FROM.replace('@', '%40') in SEND_URL
    mail = BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(sent.kwargs['json']['raw']))
    assert mail['From'].addresses[0].addr_spec == GMAIL_FROM
    assert mail['To'].addresses[0].addr_spec == 'pilot@example.test' and len(mail['To'].addresses) == 1
    assert mail['Reply-To'].addresses[0].addr_spec == 'reply@example.test'
    assert not mail.is_multipart() and not mail['Cc'] and not mail['Bcc']
    assert 'synthetic-access' not in mail.as_string()
    with pytest.raises(DeliveryFailure, match='outside_gmail_pilot'):
        adapter.send(security_email.Message('unknown@example.test', 'x', 'x', 'two'))
    assert http.post.call_count == 2
    http.post.side_effect = [response(429, {}, {'Retry-After': '900'}), requests.ReadTimeout('private')]
    with pytest.raises(DeliveryFailure) as limited:
        adapter.send(msg)
    assert (limited.value.outcome, limited.value.retry_after) == ('quota', 900)
    with pytest.raises(DeliveryFailure) as uncertain:
        adapter.send(msg)
    assert uncertain.value.outcome == 'uncertain' and 'private' not in str(uncertain.value)


def test_gmail_smtp_alternative_uses_tls_and_individual_envelope(env):
    config = env[0].config
    config.update(MAIL_PROVIDER='gmail-smtp-app-password', MAIL_LIVE_ENABLED=True, GMAIL_DAILY_LIMIT=2,
        MAIL_PILOT_RECIPIENTS='pilot@example.test', GMAIL_APP_PASSWORD='synthetic-app-only')
    smtp = MagicMock()
    provider = GmailProvider(config, smtp=smtp)
    provider.send(security_email.Message('pilot@example.test', 'Subject', 'Body', 'key'))
    assert smtp.call_args.args == ('smtp.gmail.com', 465)
    assert smtp.call_args.kwargs['context'].check_hostname
    assert smtp.return_value.send_message.call_args.kwargs == {
        'from_addr': GMAIL_FROM, 'to_addrs': ['pilot@example.test']}
    smtp.return_value.close.assert_called_once()


def test_worker_persists_retry_acceptance_and_never_retries_uncertain_sends(env, monkeypatch, caplog):
    now = [int(time.time())]
    monkeypatch.setattr(security_email, 'clock', lambda: now[0])
    security_email.enqueue(env[1]['patient'], 'change', 'synthetic-a', detail='For tests.')
    db.session.commit()

    class Mail:
        live = True
        daily_limit = 10
        recipients = {'patient@example.test'}
        calls = 0

        def accepts(self, recipient):
            return True

        def send(self, message):
            self.calls += 1
            if self.calls == 1:
                raise DeliveryFailure('gmail_quota', outcome='quota', retry_after=300)
            if self.calls == 3:
                raise requests.ReadTimeout('do-not-log@example.test')

    provider = Mail()
    assert security_email.deliver_pending(provider) == 0 and provider.calls == 1
    assert db.session.get(SecurityEmail, 'synthetic-a').state == 'pending'
    assert security_email.deliver_pending(provider) == 0 and provider.calls == 1
    now[0] += 300
    assert security_email.deliver_pending(provider) == 1
    assert db.session.get(SecurityEmail, 'synthetic-a').state == 'accepted'
    security_email.enqueue(env[1]['patient'], 'change', 'synthetic-b', detail='Test only.')
    db.session.commit()
    assert security_email.deliver_pending(provider) == 0
    assert db.session.get(SecurityEmail, 'synthetic-b').state == 'uncertain'
    now[0] += 3600
    assert security_email.deliver_pending(provider) == 0 and provider.calls == 3
    assert 'do-not-log@example.test' not in caplog.text


def decision(env, purpose, scope='practice', status='granted', recipient='patient@example.test'):
    patient = env[2][0]
    db.session.add(CommunicationDecision(institution_id=patient.institution_id, patient_id=patient.id,
        purpose=purpose, channel='email', scope=scope, status=status, destination=recipient,
        verified_at=datetime.now(timezone.utc).replace(tzinfo=None), timezone='Africa/Johannesburg',
        method='Synthetic', notice_version='test-1', recorded_by_id=env[1]['dr'].id))
    db.session.commit()


def booked(env):
    app, _, patients, *_ = env
    app.config.update(APPOINTMENT_EMAIL_ENABLED=True, APPOINTMENT_EMAIL_REMINDER_MINUTES=60)
    decision(env, 'administrative_contact')
    decision(env, 'reminders')
    _, day = approved(patients[0])
    start = utc_on(day, wall_time(8))
    client = as_user(env, 'dr')
    form = {'patient_id': patients[0].id, 'starts_at': local(start), 'service': 'Individual therapy'}
    assert client.post('/med/appointments', data=form).status_code == 302
    appointment = db.session.scalar(select(Appointment).where(Appointment.patient_id == patients[0].id,
        Appointment.starts_at == start))
    assert appointment
    return client, day, appointment, form


def appointment_jobs():
    return db.session.scalars(select(SecurityEmail).where(SecurityEmail.kind.like('appt_%'))).all()


def test_request_receipt_is_separate_and_booking_reschedule_cancel_are_deduplicated(env):
    app = env[0]
    app.config['APPOINTMENT_EMAIL_ENABLED'] = True
    future = datetime.now(timezone(timedelta(hours=2))) + timedelta(days=4)
    receipt = app.test_client().post('/book', data={'full_name': 'Synthetic request', 'email': 'guest@example.test',
        'phone': '0000000000', 'service_type': 'Individual therapy',
        'preferred_at': future.isoformat(timespec='minutes'), 'consent': 'yes'}, follow_redirects=True)
    assert b'Request received.' in receipt.data and b'not a confirmed appointment' in receipt.data
    assert not appointment_jobs()
    client, day, appointment, form = booked(env)
    assert {job.kind for job in appointment_jobs()} == {'appt_confirmed', 'appt_reminder'}
    appointment_email.queue(appointment, 'appt_confirmed')
    db.session.commit()
    assert len(appointment_jobs()) == 2
    assert client.post('/med/appointments', data=form).status_code == 302
    assert len(appointment_jobs()) == 2  # Rejected booking has no outbox side effect.
    provider = security_email.FakeMailProvider()
    assert security_email.deliver_pending(provider) == 1
    confirmation = next(iter(provider.messages.values()))
    assert confirmation.subject == 'Appointment confirmed'
    assert 'Individual therapy' not in confirmation.body and 'Scheduled time' not in confirmation.body
    decision(env, 'administrative_contact', 'appointment_details')
    assert client.post(f'/med/appointments/{appointment.id}/reschedule', data={'confirmed': 'yes',
        'reason': 'Synthetic confidential reason', 'version': appointment.schedule_version,
        'starts_at': local(utc_on(day, wall_time(8, 35)))}).status_code == 302
    assert security_email.deliver_pending(provider) == 1
    rescheduled = next(msg for msg in provider.messages.values() if msg.subject == 'Appointment rescheduled')
    assert '08:35 SAST' in rescheduled.body and 'confidential reason' not in rescheduled.body
    assert client.post(f'/med/appointments/{appointment.id}/status', data={
        'status': 'cancelled', 'version': appointment.schedule_version}).status_code == 302
    assert security_email.deliver_pending(provider) == 1
    assert any(msg.subject == 'Appointment cancelled' for msg in provider.messages.values())
    assert all(job.state == 'cancelled' for job in appointment_jobs() if job.kind == 'appt_reminder')
    assert security_email.deliver_pending(provider) == 0


@pytest.mark.parametrize('invalidate', ['status', 'version', 'recipient', 'consent', 'lead'])
def test_reminder_rechecks_current_scope_on_worker(env, invalidate):
    _, _, appointment, _ = booked(env)
    reminder = next(job for job in appointment_jobs() if job.kind == 'appt_reminder')
    reminder.next_attempt_at = 1
    db.session.commit()
    if invalidate == 'status':
        appointment.status = 'cancelled'
    elif invalidate == 'version':
        appointment.schedule_version += 1
    elif invalidate == 'recipient':
        appointment.patient.email = 'replaced@example.test'
    elif invalidate == 'consent':
        decision(env, 'reminders', '*', 'withdrawn')
    else:
        env[0].config['APPOINTMENT_EMAIL_REMINDER_MINUTES'] = 45
    db.session.commit()
    provider = security_email.FakeMailProvider()
    security_email.deliver_pending(provider)
    assert not any(message.subject == 'Appointment reminder' for message in provider.messages.values())
    assert reminder.state == 'cancelled'
    assert db.session.get(AppointmentEmail, reminder.dedupe_key)


def test_email_withdrawal_does_not_revive_queued_appointments_or_stop_security(env):
    _, _, appointment, _ = booked(env)
    client = as_user(env, 'patient')
    path = '/med/preferences'
    preferences = {'patient_id': appointment.patient_id, 'communication_consent': 'yes'}
    assert client.post(path, data={**preferences, 'channels': ['portal']}).status_code == 302
    assert client.post(path, data={**preferences, 'channels': ['portal', 'email']}).status_code == 302

    for job in appointment_jobs():
        job.next_attempt_at = 1
    security_email.enqueue(env[1]['patient'], 'change', 'synthetic-security-withdrawal', detail='Synthetic.')
    db.session.commit()
    provider = security_email.FakeMailProvider()
    assert security_email.deliver_pending(provider) == 1
    assert all(job.state == 'cancelled' for job in appointment_jobs())
    assert {message.subject for message in provider.messages.values()} == {'Ramosolo account security change'}


def test_marketing_purpose_cannot_enter_or_render_from_transactional_mail(env):
    from types import SimpleNamespace

    with pytest.raises(ValueError, match='Unsupported account email purpose'):
        security_email.enqueue(env[1]['patient'], 'marketing', 'synthetic-marketing')
    assert security_email.render(SimpleNamespace(kind='marketing')) is None
    assert db.session.get(SecurityEmail, 'synthetic-marketing') is None


PHONE_PATH = '/auth/security/phone'
FIRST = '+12025550123'
SECOND = '+12025550124'
PASSWORD = 'Testing-password-123'


@pytest.fixture
def sms_case(env, monkeypatch):
    app, users, *_ = env
    now = [int(time.time())]
    clock = lambda: now[0]
    monkeypatch.setattr(phone_verification, 'clock', clock)
    monkeypatch.setattr(multi_factor, 'clock', clock)
    monkeypatch.setattr(portal_sessions, 'clock', clock)
    key = Fernet.generate_key()
    app.config.update(SMS_PROVIDER='fake', SMS_POLICY_APPROVED=True, SMS_ELIGIBLE_ROLES='dr,patient',
        SMS_ALLOWED_REGIONS='ZA,US', SMS_DAILY_MAX=20, SMS_KEY=key,
        SMS_LIMIT_KEY='synthetic-only-limit-key-for-local-tests', AUTH_MFA_KEY=key,
        AUTH_REQUIRE_STAFF_MFA=True)
    seeds = {}
    for role in ('dr', 'patient'):
        seed = pyotp.random_base32()
        seeds[role] = seed
        db.session.add(Authenticator(user_id=users[role].id, encrypted_secret=Fernet(key).encrypt(seed.encode()),
                                     last_counter=0))
    db.session.commit()
    return app, users, now, seeds, FakeSMSProvider(clock)


def totp(case, role='dr'):
    return pyotp.TOTP(case[3][role]).at(datetime.fromtimestamp(case[2][0], timezone.utc))


def sms_login(case, role='dr'):
    case[2][0] += 30
    client = case[0].test_client()
    assert password_login(client, role).location.endswith('/auth/mfa')
    assert client.get(PHONE_PATH).location.endswith('/auth/login')
    assert client.post('/auth/mfa', data={'code': totp(case, role)}).location.endswith('/med')
    case[2][0] += 30
    return client


def start_phone(case, client, number=FIRST, role='dr'):
    case[0].extensions['portal_fake_sms'] = case[4]
    result = client.post(PHONE_PATH, data={'action': 'start', 'phone': number,
        'password': PASSWORD, 'code': totp(case, role)})
    assert result.status_code == 302
    return db.session.get(PhoneChallenge, case[1][role].id, populate_existing=True)


def test_sms_normalization_resend_session_binding_and_expiry(sms_case):
    app, users, now, _, provider = sms_case
    assert phone_verification.normalize('+27 82 123 4567', {'ZA'}) == '+27821234567'
    assert phone_verification.normalize('0821234567', {'ZA'}) is None
    assert phone_verification.normalize(FIRST, {'ZA'}) is None
    client = sms_login(sms_case)
    challenge = start_phone(sms_case, client, '+1 202-555-0123')
    body = client.get(PHONE_PATH).data
    assert b'0123' in body and FIRST.encode() not in body
    ref, code, _ = provider.challenges[FIRST]
    data = {'action': 'resend', 'challenge_id': challenge.challenge_id}
    client.post(PHONE_PATH, data=data)
    assert challenge.sends == 1
    now[0] += 60
    client.post(PHONE_PATH, data=data)
    assert challenge.sends == 2 and provider.challenges[FIRST][:2] == (ref, code)
    other_session = sms_login(sms_case)
    other_session.post(PHONE_PATH, data={'action': 'check', 'challenge_id': challenge.challenge_id, 'code': code})
    assert db.session.get(VerifiedPhone, users['dr'].id) is None
    now[0] = challenge.expires_at
    client.post(PHONE_PATH, data={'action': 'check', 'challenge_id': challenge.challenge_id, 'code': code})
    assert db.session.get(VerifiedPhone, users['dr'].id) is None
    assert not any(job.kind == 'sms' for job in db.session.scalars(select(SecurityEmail)))


def test_sms_verification_and_phone_change_notify_old_channel_and_never_replace_staff_mfa(sms_case):
    app, users, _, _, provider = sms_case
    client = sms_login(sms_case)
    challenge = start_phone(sms_case, client)
    code = provider.challenges[FIRST][1]
    copied = copy_cookie(app, client)
    payload = {'action': 'check', 'challenge_id': challenge.challenge_id, 'code': code}
    assert client.post(PHONE_PATH, data=payload).location.endswith('/auth/login')
    assert db.session.get(VerifiedPhone, users['dr'].id) and db.session.get(Authenticator, users['dr'].id)
    assert copied.post(PHONE_PATH, data=payload).location.endswith('/auth/login')
    client = sms_login(sms_case)
    assert client.post(PHONE_PATH, data={'action': 'start', 'phone': SECOND, 'password': PASSWORD}).status_code == 302
    assert SECOND not in provider.challenges and not provider.notices
    challenge = start_phone(sms_case, client, SECOND)
    assert provider.notices == [FIRST]
    assert client.post(PHONE_PATH, data={'action': 'check', 'challenge_id': challenge.challenge_id,
        'code': provider.challenges[SECOND][1]}).location.endswith('/auth/login')
    assert db.session.get(Authenticator, users['dr'].id)
    app.config['SMS_POLICY_APPROVED'] = False
    assert password_login(client, 'dr').location.endswith('/auth/mfa')
    assert client.get('/med').location.endswith('/auth/login')


def test_sms_provider_failure_and_destination_lease_fail_closed(sms_case):
    app, users, _, _, provider = sms_case
    client = sms_login(sms_case)
    challenge = start_phone(sms_case, client)
    patient = sms_login(sms_case, 'patient')
    assert start_phone(sms_case, patient, FIRST, 'patient') is None

    def fail(*args):
        raise ProviderUnavailable('synthetic-private')

    provider.check = fail
    client.post(PHONE_PATH, data={'action': 'check', 'challenge_id': challenge.challenge_id,
        'code': '123456'})
    assert challenge.state == 'failed' and db.session.get(VerifiedPhone, users['dr'].id) is None
    assert not any(job.dedupe_key.startswith('phone:') for job in db.session.scalars(select(SecurityEmail)))


def test_sms_budget_blocks_resend_and_other_accounts(sms_case):
    app, _, now, _, provider = sms_case
    app.config['SMS_DAILY_MAX'] = 1
    doctor = sms_login(sms_case)
    row = start_phone(sms_case, doctor)
    now[0] += 60
    doctor.post(PHONE_PATH, data={'action': 'resend', 'challenge_id': row.challenge_id})
    assert row.sends == 1
    patient = sms_login(sms_case, 'patient')
    assert start_phone(sms_case, patient, SECOND, 'patient') is None
    assert set(provider.challenges) == {FIRST}


def test_concurrent_sms_submissions_use_the_provider_once(sms_case):
    app, users, _, _, provider = sms_case
    client = sms_login(sms_case)
    challenge = start_phone(sms_case, client)
    payload = {'action': 'check', 'challenge_id': challenge.challenge_id, 'code': provider.challenges[FIRST][1]}
    other = copy_cookie(app, client)
    entered, finish = threading.Event(), threading.Event()
    calls = []
    original = provider.check

    def wait_then_check(*args):
        calls.append(1)
        entered.set()
        assert finish.wait(5)
        return original(*args)

    provider.check = wait_then_check
    db.session.remove()
    with ThreadPoolExecutor(max_workers=2) as threads:
        attempt = threads.submit(client.post, PHONE_PATH, data=payload)
        assert entered.wait(5)
        try:
            denied = threads.submit(other.post, PHONE_PATH, data=payload).result(timeout=5)
        finally:
            finish.set()
        assert attempt.result(timeout=5).location.endswith('/auth/login')
    assert denied.location.endswith(PHONE_PATH) and calls == [1]
    assert db.session.get(VerifiedPhone, users['dr'].id)


def test_twilio_adapter_matches_verified_reference_and_never_accepts_delivery_status(env):
    config = env[0].config
    service, reference = 'VA' + '1' * 32, 'VE' + '2' * 32
    config.update(TWILIO_VERIFY_SERVICE_SID=service, TWILIO_ACCOUNT_SID='AC' + '3' * 32,
        TWILIO_API_KEY='SK' + '4' * 32, TWILIO_API_SECRET='synthetic-token',
        TWILIO_SECURITY_MESSAGING_SERVICE_SID='MG' + '5' * 32)
    http = MagicMock()
    identity = {'sid': reference, 'to': FIRST, 'service_sid': service, 'channel': 'sms',
                'account_sid': config['TWILIO_ACCOUNT_SID']}
    http.post.side_effect = [response(201, {**identity, 'status': 'pending'}),
                            response(200, {**identity, 'status': 'delivered'}),
                            response(200, {**identity, 'status': 'approved', 'valid': True}),
                            response(200, {**identity, 'status': 'approved', 'to': SECOND})]
    adapter = TwilioVerifyProvider(config, http=http)
    assert adapter.send(FIRST) == reference
    assert http.post.call_args.kwargs['data']['RiskCheck'] == 'enable'
    assert not adapter.check(reference, FIRST, '123456')
    assert adapter.check(reference, FIRST, '123456')
    with pytest.raises(ProviderUnavailable):
        adapter.check(reference, FIRST, '123456')
