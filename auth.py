from datetime import datetime, timedelta, timezone
from flask import Blueprint, current_app, g, render_template, request, redirect, url_for, flash, session, abort
from flask_login import current_user, login_required
from sqlalchemy import delete, select
from werkzeug.security import check_password_hash, generate_password_hash
from extensions import db
from models import AccountVerification, Authenticator, PendingAuthentication, PortalSession, User
import portal_sessions
import account_verification
import multi_factor
from security_email import enqueue

bp = Blueprint('auth', __name__, url_prefix='/auth')
DUMMY_HASH = generate_password_hash('not-a-real-account-password')


def browser_description():
    agent = request.headers.get('User-Agent', '')[:512].lower()
    browser = next((name for marker, name in (
        ('edg/', 'Edge'), ('opr/', 'Opera'), ('firefox/', 'Firefox'), ('fxios/', 'Firefox'),
        ('chrome/', 'Chrome'), ('crios/', 'Chrome'), ('safari/', 'Safari')) if marker in agent), 'Unknown browser')
    os = next((name for marker, name in (
        ('iphone', 'iOS'), ('ipad', 'iPadOS'), ('android', 'Android'), ('windows', 'Windows'),
        ('mac os', 'macOS'), ('linux', 'Linux')) if marker in agent), 'unknown operating system')
    return f'{browser} on {os}'


def finish_login(user, *, mfa_method=None):
    token = portal_sessions.create_session(user, mfa_at=portal_sessions.clock() if mfa_method else None,
                                           mfa_method=mfa_method)
    enqueue(user, 'login', 'login:' + portal_sessions.digest(token), detail=browser_description())
    db.session.commit()
    portal_sessions.activate_session(user, token)


def begin_login(user):
    if not user.enabled or not account_verification.email_allowed(user):
        flash('Unable to sign in. If your account is new, confirm your email first.', 'error')
        return redirect(url_for('auth.resend_verification'))
    factor = db.session.get(Authenticator, user.id)
    if factor or multi_factor.requires_mfa(user.id):
        token = multi_factor.start(user, 'challenge' if factor else 'enroll')
        if not token:
            db.session.rollback()
            flash('Authenticator sign-in is unavailable. Contact the practice.', 'error')
            return redirect(url_for('auth.help_signing_in'))
        db.session.commit()
        session.clear()
        session['mfa_pending'] = token
        return redirect(url_for('auth.mfa'))
    finish_login(user)
    return redirect(url_for('med.dashboard'))


def record_password_failure(user, now):
    user.failed_logins += 1
    if user.failed_logins >= 5:
        user.locked_until = now + timedelta(minutes=15)
        user.failed_logins = 0


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('med.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        valid_input=bool(email and '@' in email and len(email)<=254 and 1<=len(password)<=512)
        user = db.session.scalar(select(User).where(User.email == email).with_for_update()
                                 .execution_options(populate_existing=True)) if valid_input else None
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        valid = check_password_hash(user.password_hash if user else DUMMY_HASH, password if valid_input else '')
        blocked = user and user.locked_until and user.locked_until > now
        if user and user.enabled and valid and not blocked:
            user.failed_logins = 0
            user.locked_until = None
            if not account_verification.email_allowed(user):
                state = db.session.get(AccountVerification, user.id)
                if state is None and account_verification.valid_address(user.email):
                    account_verification.issue(user, user.email, initial=True)
                db.session.commit()
            return begin_login(user)
        if user and not blocked:
            record_password_failure(user, now)
            db.session.commit()
        flash('Unable to sign in. Check your details or try again later.', 'error')
    return render_template('auth/login.html')


@bp.post('/logout')
def logout():
    portal_sessions.sign_out()
    if request.accept_mimetypes.best == 'application/json':
        return '', 204
    return redirect(url_for('med.home'))


@bp.get('/session-status')
def session_status():
    if not current_user.is_authenticated:
        return {'authenticated': False}, 401
    expires_at, absolute = portal_sessions.deadlines(g.portal_session)
    return {'authenticated': True, 'now': portal_sessions.clock(), 'expires_at': expires_at,
            'absolute_at': absolute, 'warning_seconds': current_app.config['AUTH_WARNING_SECONDS'],
            'page': portal_sessions.page_identity(g.portal_session)}


@bp.post('/session-extend')
def session_extend():
    if not current_user.is_authenticated or not portal_sessions.extend(g.portal_session):
        return {'authenticated': False}, 401
    return session_status()


@bp.route('/verify', methods=['GET', 'POST'])
def verify_email():
    if request.method == 'POST':
        if account_verification.confirm(request.form.get('token', '')):
            flash('Email confirmed. You can now sign in if your account has been activated.', 'success')
            return redirect(url_for('auth.login'))
        flash('This link could not be used. Request a new confirmation email.', 'error')
        return redirect(url_for('auth.resend_verification'))
    return render_template('auth/verify.html', token=request.args.get('t', '')[:108])


@bp.route('/verification', methods=['GET', 'POST'])
def resend_verification():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if account_verification.valid_address(email):
            user = db.session.scalar(select(User).where(User.email == email).with_for_update())
            if user and user.enabled:
                state = db.session.get(AccountVerification, user.id)
                if state and state.requested_email:
                    account_verification.issue(user, state.requested_email)
                    db.session.commit()
        flash('If the account needs confirmation and a resend is available, a message will be queued.', 'success')
        return redirect(url_for('auth.resend_verification'))
    return render_template('auth/resend_verification.html')


@bp.get('/help')
def help_signing_in():
    return render_template('auth/help.html', support_phone=current_app.config['AUTH_SUPPORT_PHONE'])


@bp.route('/mfa', methods=['GET', 'POST'])
def mfa():
    user, pending = multi_factor.pending(lock=request.method == 'POST')
    if not pending:
        flash('Sign in again to continue.', 'error')
        return redirect(url_for('auth.login'))
    secret = multi_factor.read_secret(pending.encrypted_secret) if pending.encrypted_secret else None
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        factor = db.session.get(Authenticator, user.id, with_for_update=True)
        if pending.mode == 'challenge':
            proof = factor and multi_factor.factor_proof(factor, code, allow_recovery=True)
            counter = None
        else:
            counter = multi_factor.counter_for(secret, code)
            proof = counter is not None and (pending.mode == 'replace' or not factor)
        if proof:
            claimed = db.session.execute(delete(PendingAuthentication).where(
                PendingAuthentication.token_hash == pending.token_hash)).rowcount
            if claimed != 1:
                db.session.rollback()
                abort(409)
            if counter is not None:
                recovery = multi_factor.register_factor(user, pending, counter)
                state = db.session.get(AccountVerification, user.id)
                if state:
                    state.mfa_reenroll_required = False
                user.session_version += 1
                enqueue(user, 'change', 'factor:' + pending.token_hash,
                        detail='An authenticator app was configured.')
            else:
                recovery = None
                if proof == 'recovery':
                    enqueue(user, 'change', 'recovery:' + pending.token_hash,
                            detail='A single-use recovery code was used.')
            finish_login(user, mfa_method='recovery' if proof == 'recovery' else 'totp')
            if recovery:
                return render_template('auth/recovery_codes.html', codes=recovery)
            return redirect(url_for('med.dashboard'))
        pending.attempts += 1
        db.session.commit()
        flash('The code could not be accepted. Try again or contact the practice.', 'error')
    return render_template('auth/mfa.html', mode=pending.mode, secret=secret)


def reauthenticate(user, factor, *, allow_recovery=False, recent_recovery=False):
    password = request.form.get('password', '')
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if user.locked_until and user.locked_until > now:
        return False
    if not 1 <= len(password) <= 512 or not user.check_password(password):
        record_password_failure(user, now)
        db.session.commit()
        return False
    code = request.form.get('code', '').strip()
    if factor and not (recent_recovery and not code) and not multi_factor.factor_proof(
            factor, code, allow_recovery=allow_recovery):
        db.session.commit()
        return False
    user.failed_logins = 0
    user.locked_until = None
    return True


@bp.route('/security', methods=['GET', 'POST'])
@login_required
def security_settings():
    user = current_user._get_current_object()
    factor = db.session.get(Authenticator, user.id)
    portal = g.portal_session
    recent_recovery = portal.mfa_method == 'recovery' and 0 <= portal_sessions.clock() - portal.mfa_at < 300
    if request.method == 'GET':
        from phone_verification import enabled
        return render_template('auth/security_settings.html', has_factor=factor is not None,
                               required=multi_factor.staff_requires_mfa(user.id), recent_recovery=recent_recovery,
                               phone_enabled=enabled(g.membership))
    action = request.form.get('action')
    if action not in ('enroll', 'replace', 'disable', 'email', 'password'):
        abort(400)
    user = db.session.get(User, user.id, with_for_update=True, populate_existing=True)
    if not user or user.get_id() != session.get('_user_id') or not user.enabled:
        abort(401)
    factor = db.session.get(Authenticator, user.id, with_for_update=True, populate_existing=True)
    if not reauthenticate(user, factor, allow_recovery=action == 'replace',
                          recent_recovery=action == 'replace' and recent_recovery):
        flash('We could not confirm your authentication. Try again later.', 'error')
        return redirect(url_for('auth.security_settings'))
    if action in ('enroll', 'replace'):
        if (action == 'enroll') == (factor is not None):
            abort(400)
        token = multi_factor.start(user, action)
        if not token:
            abort(503)
        claimed = db.session.execute(delete(PortalSession).where(PortalSession.token_hash == portal.token_hash,
            PortalSession.idle_expires_at > portal_sessions.clock(),
            PortalSession.absolute_expires_at > portal_sessions.clock())).rowcount
        if claimed != 1:
            abort(401)
        db.session.commit()
        session.clear()
        session['mfa_pending'] = token
        return redirect(url_for('auth.mfa'))
    if action == 'email':
        email = request.form.get('new_email', '').strip().lower()
        if (not account_verification.valid_address(email) or email == user.email or
                db.session.scalar(select(User.id).where(User.email == email))):
            abort(400)
        state = db.session.get(AccountVerification, user.id, with_for_update=True)
        if state is None:
            # Preserve the existing address while its replacement is pending.
            state = AccountVerification(user_id=user.id,
                                        resend_after=0, window_started_at=0, send_count=0)
            db.session.add(state)
            db.session.flush()
        if account_verification.issue(user, email):
            enqueue(user, 'change', 'email-request:' + state.verification_id,
                    detail='A change to your sign-in email address was requested.')
            flash('Confirm the new address using the message sent there.', 'success')
        else:
            flash('An email was requested recently. Try again later.', 'error')
        db.session.commit()
        return redirect(url_for('auth.security_settings'))
    if action == 'disable':
        if not factor or multi_factor.staff_requires_mfa(user.id):
            abort(403)
        db.session.delete(factor)
        user.session_version += 1
        detail = 'The authenticator app was disabled.'
    else:
        password = request.form.get('new_password', '')
        if not 12 <= len(password) <= 128 or password != request.form.get('confirm_password'):
            abort(400)
        user.set_password(password)
        detail = 'The sign-in password changed.'
    enqueue(user, 'change', f'credentials:{user.id}:{user.session_version}', detail=detail)
    db.session.commit()
    portal_sessions.sign_out()
    flash('Security settings updated. Sign in again to continue.', 'success')
    return redirect(url_for('auth.login'))


@bp.route('/security/phone', methods=['GET', 'POST'])
@login_required
def phone_settings():
    import phone_verification as verification
    from models import PhoneChallenge, VerifiedPhone

    if not verification.enabled(g.membership):
        abort(404)
    try:
        config = verification.settings()
        provider = verification.get_provider()
    except (TypeError, ValueError):
        abort(503)
    portal = g.portal_session
    user_id = current_user.id
    institution_id = g.membership.institution_id
    if request.method == 'GET':
        try:
            phone = verification.masked_phone(config[0], db.session.get(VerifiedPhone, user_id))
            row = db.session.get(PhoneChallenge, user_id)
            pending = row if (verification.current(row, portal, institution_id)
                              and row.state == 'pending') else None
            masked = verification.masked_phone(config[0], pending)
        except ValueError:
            abort(503)
        return render_template('auth/phone_settings.html', phone=phone,
                               challenge_id=pending.challenge_id if pending else None, pending_phone=masked)
    action = request.form.get('action')
    challenge_id = request.form.get('challenge_id', '')
    if action == 'check':
        try:
            approved = verification.check(user_id, portal, institution_id, provider, config,
                                          challenge_id, request.form.get('code', '').strip())
        except ValueError:
            approved = False
        if approved:
            portal_sessions.sign_out()
            flash('Phone ownership verified. Sign in again to continue.', 'success')
            return redirect(url_for('auth.login'))
        flash('The code could not be accepted. Check the code or start again after it expires.', 'error')
        return redirect(url_for('auth.phone_settings'))

    if action not in ('start', 'resend'):
        abort(400)
    user = db.session.get(User, user_id, with_for_update=True, populate_existing=True)
    if not user or not user.enabled or user.get_id() != session.get('_user_id'):
        abort(401)
    destination = None
    if action == 'start':
        factor = db.session.get(Authenticator, user_id, with_for_update=True, populate_existing=True)
        if not factor or not reauthenticate(user, factor):
            flash('Confirm your password and current authenticator code first.', 'error')
            return redirect(url_for('auth.phone_settings'))
        destination = request.form.get('phone', '')
    try:
        result = verification.send(user, portal, institution_id, provider, config,
                                   submitted=destination, challenge_id=challenge_id)
    except ValueError:
        result = 'unavailable'
    if result == 'sent':
        flash('A verification message was accepted for sending.', 'success')
    else:
        db.session.rollback()
        flash('The request could not be completed. Check the number, wait and try again, or contact the practice.', 'error')
    return redirect(url_for('auth.phone_settings'))
