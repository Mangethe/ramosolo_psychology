import re
import time
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pyotp
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

import account_verification
import multi_factor
import portal_sessions
import security_email
from extensions import db
from models import AccountVerification, Authenticator, Institution, Membership, PortalSession, SecurityEmail
from test_medical import as_user, env


PASSWORD = 'Testing-password-123'


def password_login(client, role='patient', **kwargs):
    return client.post('/auth/login', data={'email': role + '@example.test', 'password': PASSWORD}, **kwargs)


def copy_cookie(app, client):
    other = app.test_client()
    name = app.config['SESSION_COOKIE_NAME']
    other.set_cookie(name, client.get_cookie(name).value)
    return other


def csrf(response):
    return re.search(rb'name="csrf_token" value="([^"]+)"', response.data)[1].decode()


def verify_token(state):
    return account_verification.verification_token(state.verification_id, state.user_id, state.requested_email)


def jobs(kind):
    return db.session.scalars(select(SecurityEmail).where(SecurityEmail.kind == kind)).all()


def test_polling_idle_absolute_and_logout_across_copied_cookies(env, monkeypatch):
    app = env[0]
    now = [int(time.time())]
    monkeypatch.setattr(portal_sessions, 'clock', lambda: now[0])
    app.config.update(WTF_CSRF_ENABLED=True, AUTH_IDLE_TIMEOUT=timedelta(seconds=30),
                      AUTH_WARNING_SECONDS=10, PERMANENT_SESSION_LIFETIME=timedelta(seconds=70))
    client = app.test_client()
    login_token = csrf(client.get('/auth/login'))
    result = client.post('/auth/login', data={'email': 'patient@example.test', 'password': PASSWORD,
                                             'csrf_token': login_token})
    assert result.status_code == 302
    token = csrf(client.get('/med'))
    other = copy_cookie(app, client)
    initial = other.get('/auth/session-status').json
    assert initial['expires_at'] == now[0] + 30
    assert initial['absolute_at'] == now[0] + 70
    now[0] += 25
    assert client.get('/med/appointments').status_code == 200
    assert other.get('/auth/session-status').json['expires_at'] == initial['expires_at']
    assert other.post('/auth/session-extend').status_code == 400
    assert client.post('/auth/session-extend', headers={'X-CSRFToken': token}).json['expires_at'] == now[0] + 30
    assert other.get('/auth/session-status').json['expires_at'] == now[0] + 30
    now[0] += 25
    assert other.post('/auth/session-extend', headers={'X-CSRFToken': token}).json['expires_at'] == initial['absolute_at']
    now[0] = initial['absolute_at']
    assert client.get('/auth/session-status').status_code == 401
    assert other.post('/auth/session-extend', headers={'X-CSRFToken': token}).status_code == 401
    assert other.get('/med/appointments').status_code == 302
    new_token = csrf(client.get('/auth/login'))
    client.post('/auth/login', data={'email': 'patient@example.test', 'password': PASSWORD, 'csrf_token': new_token})
    token = csrf(client.get('/med'))
    copied = copy_cookie(app, client)
    assert client.post('/auth/logout', headers={'X-CSRFToken': token, 'Accept': 'application/json'}).status_code == 204
    assert copied.get('/auth/session-status').status_code == 401
    assert copied.get('/med').status_code == 302


def test_idle_without_extension_revokes_access_and_institution_rotation_rejects_old_cookie(env, monkeypatch):
    app, users, patients, *_ = env
    now = [int(time.time())]
    monkeypatch.setattr(portal_sessions, 'clock', lambda: now[0])
    client = as_user(env, 'patient')
    deadline = client.get('/auth/session-status').json['expires_at']
    now[0] = deadline - 1
    assert client.get('/auth/session-status').status_code == 200
    now[0] += 1
    assert client.get('/med/appointments').status_code == 302
    second = Institution(name='Synthetic second assignment', kind='medical')
    db.session.add(second)
    db.session.flush()
    db.session.add(Membership(user_id=users['patient'].id, institution_id=second.id, role='patient'))
    db.session.commit()
    client = as_user(env, 'patient')
    assert b'class="status scheduled"' in client.get('/med/appointments').data
    old = copy_cookie(app, client)
    absolute = old.get('/auth/session-status').json['absolute_at']
    assert client.post('/institutions', data={'institution_id': second.id}).status_code == 302
    assert old.get('/auth/session-status').status_code == 401
    assert client.get('/auth/session-status').json['absolute_at'] == absolute
    assert b'class="status scheduled"' not in client.get('/med/appointments').data
    assert client.post('/institutions', data={'institution_id': patients[2].institution_id}).status_code == 403


def test_verification_get_resend_expiry_single_use_and_welcome(env, monkeypatch, caplog):
    app, users, *_ = env
    user = users['patient']
    now = [int(time.time())]
    monkeypatch.setattr(account_verification, 'clock', lambda: now[0])
    monkeypatch.setattr(security_email, 'clock', lambda: now[0])
    app.config.update(AUTH_VERIFICATION_SECONDS=120, AUTH_PUBLIC_URL='https://portal.example.test')
    db.session.delete(db.session.get(AccountVerification, user.id))
    db.session.commit()
    assert account_verification.issue(user, user.email, initial=True)
    db.session.commit()
    state = db.session.get(AccountVerification, user.id)
    first = verify_token(state)
    assert first != state.token_hash and first not in jobs('verify')[0].detail
    client = app.test_client()
    assert password_login(client).headers['Location'].endswith('/auth/verification')
    assert client.get('/med').status_code == 302
    assert client.get('/auth/verify', query_string={'t': first}).status_code == 200
    assert state.verified_at is None
    for email in (user.email, 'unknown@example.test'):
        assert client.post('/auth/verification', data={'email': email}).status_code == 302
    assert len(jobs('verify')) == 1
    now[0] += 60
    client.post('/auth/verification', data={'email': user.email})
    second = verify_token(state)
    assert second != first
    assert client.post('/auth/verify', data={'token': first}).headers['Location'].endswith('/verification')
    now[0] += 120
    assert client.post('/auth/verify', data={'token': second}).headers['Location'].endswith('/verification')
    client.post('/auth/verification', data={'email': user.email})
    third = verify_token(state)

    class Unavailable:
        def send(self, message):
            raise RuntimeError(message.body)

    assert security_email.deliver_pending(Unavailable()) == 0
    assert third not in caplog.text and user.email not in caplog.text
    now[0] += 60
    assert security_email.deliver_pending(security_email.FakeMailProvider()) == 1
    client.post('/auth/verification', data={'email': user.email})
    assert len(jobs('verify')) == 3
    now[0] += 3600
    client.post('/auth/verification', data={'email': user.email})
    token = verify_token(state)
    provider = security_email.FakeMailProvider()
    assert security_email.deliver_pending(provider) == 1
    message = next(iter(provider.messages.values()))
    assert f'https://portal.example.test/auth/verify?t={token}' in message.body
    assert client.get('/auth/verify', query_string={'t': token}).status_code == 200
    assert client.post('/auth/verify', data={'token': token}).headers['Location'].endswith('/auth/login')
    assert client.post('/auth/verify', data={'token': token}).headers['Location'].endswith('/verification')
    assert state.verified_email == user.email and len(jobs('welcome')) == 1
    assert password_login(client).headers['Location'].endswith('/med')
    assert client.get('/med/appointments').status_code == 200
    assert client.post('/auth/logout').status_code == 302
    assert state.verified_email == user.email
    assert security_email.deliver_pending(provider) == 2
    assert security_email.deliver_pending(provider) == 0
    assert any('Africa/Johannesburg' in message.body for message in provider.messages.values())


@pytest.mark.parametrize('role', ['admin', 'dr', 'nurse', 'dr_assist', 'patient'])
def test_each_role_after_complete_authentication_keeps_scope(env, role):
    app, _, patients, *_ = env
    app.config.update(AUTH_REQUIRE_STAFF_MFA=True, AUTH_MFA_KEY=Fernet.generate_key())
    client = app.test_client()
    result = password_login(client, role)
    if role != 'patient':
        assert result.headers['Location'].endswith('/auth/mfa')
        assert not jobs('login')
        for path in ('/med', '/med/appointments', '/med/charts/continuity', '/admin/users'):
            assert client.get(path).status_code == 302
        assert client.post('/med/exports', data={'resource': 'diagnoses', 'patient_id': patients[2].id}).status_code == 302
        secret = re.search(rb'<code>([A-Z2-7]+)</code>', client.get('/auth/mfa').data)[1].decode()
        assert b'Save your recovery codes' in client.post('/auth/mfa', data={'code': pyotp.TOTP(secret).now()}).data
    assert len(jobs('login')) == 1
    dashboard = client.get('/med')
    assert dashboard.status_code == 200 and b'FOREIGN PRIVATE PATIENT' not in dashboard.data
    assert client.post('/institutions', data={'institution_id': patients[2].institution_id}).status_code == 403
    if role == 'patient':
        assert client.get('/med/patients').status_code == 403
        assert len(re.findall(b'class="status scheduled"', client.get('/med/appointments').data)) == 1
    else:
        assert client.get(f'/med/patients/{patients[2].id}').status_code == 404


def test_mfa_replay_recovery_rate_limit_and_recent_proof(env, monkeypatch):
    app, users, *_ = env
    now = [int(time.time())]
    monkeypatch.setattr(multi_factor, 'clock', lambda: now[0])
    app.config.update(AUTH_REQUIRE_STAFF_MFA=True, AUTH_MFA_KEY=Fernet.generate_key())
    client = app.test_client()
    password_login(client, 'dr')
    pending_copy = copy_cookie(app, client)
    secret = re.search(rb'<code>([A-Z2-7]+)</code>', client.get('/auth/mfa').data)[1].decode()
    code = pyotp.TOTP(secret).at(now[0])
    response = client.post('/auth/mfa', data={'code': code})
    recovery = re.search(rb'<li><code>([A-Za-z0-9_-]{22})</code></li>', response.data)[1].decode()
    assert secret.encode() not in db.session.get(Authenticator, users['dr'].id).encrypted_secret
    assert pending_copy.get('/auth/mfa').headers['Location'].endswith('/auth/login')
    assert client.post('/auth/security', data={'action': 'password', 'password': PASSWORD,
        'new_password': 'New-password-synthetic', 'confirm_password': 'New-password-synthetic'}).status_code == 302
    assert users['dr'].check_password(PASSWORD)
    client.post('/auth/logout')
    password_login(client, 'dr')
    assert b'The code could not be accepted' in client.post('/auth/mfa', data={'code': code}).data
    assert client.get('/med').status_code == 302
    assert client.post('/auth/mfa', data={'code': recovery}).headers['Location'].endswith('/med')
    client.post('/auth/logout')
    password_login(client, 'dr')
    for _ in range(5):
        assert b'The code could not be accepted' in client.post('/auth/mfa', data={'code': recovery}).data
    password_login(client, 'dr')
    now[0] += 30
    assert b'The code could not be accepted' in client.post('/auth/mfa', data={'code': pyotp.TOTP(secret).at(now[0])}).data
    assert client.get('/med').status_code == 302


def test_patient_can_enrol_and_replace_lost_authenticator_after_recovery(env, monkeypatch):
    app = env[0]
    now = [int(time.time())]
    monkeypatch.setattr(multi_factor, 'clock', lambda: now[0])
    app.config['AUTH_MFA_KEY'] = Fernet.generate_key()
    client = app.test_client()
    assert password_login(client).headers['Location'].endswith('/med')
    old = copy_cookie(app, client)
    assert client.post('/auth/security', data={'action': 'enroll', 'password': PASSWORD}).headers[
        'Location'].endswith('/auth/mfa')
    assert old.get('/med').status_code == 302
    secret = re.search(rb'<code>([A-Z2-7]+)</code>', client.get('/auth/mfa').data)[1].decode()
    first = client.post('/auth/mfa', data={'code': pyotp.TOTP(secret).at(now[0])})
    old_codes = re.findall(rb'<li><code>([A-Za-z0-9_-]{22})</code></li>', first.data)
    assert len(old_codes) == 10
    client.post('/auth/logout')
    assert password_login(client).headers['Location'].endswith('/auth/mfa')
    assert client.post('/auth/mfa', data={'code': old_codes[0].decode()}).headers['Location'].endswith('/med')
    assert client.post('/auth/security', data={'action': 'disable', 'password': PASSWORD}).headers[
        'Location'].endswith('/auth/security')
    assert client.post('/auth/security', data={'action': 'replace', 'password': PASSWORD}).headers[
        'Location'].endswith('/auth/mfa')
    new_secret = re.search(rb'<code>([A-Z2-7]+)</code>', client.get('/auth/mfa').data)[1].decode()
    assert new_secret != secret
    second = client.post('/auth/mfa', data={'code': pyotp.TOTP(new_secret).at(now[0])})
    assert b'Save your recovery codes' in second.data
    client.post('/auth/logout')
    password_login(client)
    assert b'The code could not be accepted' in client.post('/auth/mfa', data={'code': old_codes[1].decode()}).data


def test_login_and_setting_emails_use_trusted_origin_and_generic_browser(env):
    app, users, *_ = env
    app.config['AUTH_PUBLIC_URL'] = 'https://portal.example.test'
    client = app.test_client()
    assert password_login(client, headers={'Host': 'untrusted.example.test',
        'User-Agent': 'Chrome/10 on Windows INJECT_MUST_NOT_APPEAR'}).status_code == 302
    provider = security_email.FakeMailProvider()
    assert security_email.deliver_pending(provider) == 1
    # The synthetic Host has its own cookie. Authenticate on localhost to change settings.
    password_login(client)
    assert client.post('/auth/security', data={'action': 'email', 'password': PASSWORD,
        'new_email': 'changed@example.test'}).status_code == 302
    state = db.session.get(AccountVerification, users['patient'].id)
    assert state.requested_email == 'changed@example.test'
    assert client.get('/med').status_code == 200
    old = copy_cookie(app, client)
    assert client.post('/auth/verify', data={'token': verify_token(state)}).headers['Location'].endswith('/auth/login')
    assert old.get('/med').status_code == 302
    security_email.deliver_pending(provider)
    old_login_jobs = [job for job in jobs('login') if job.state == 'cancelled']
    assert len(old_login_jobs) == 1
    bodies = [message.body for message in provider.messages.values()]
    assert any('Chrome on Windows' in body and 'UTC' in body and 'Africa/Johannesburg' in body for body in bodies)
    assert any('address was requested' in body for body in bodies)
    for body in bodies:
        assert 'https://portal.example.test/auth/help' in body
        assert 'untrusted.example.test' not in body and 'INJECT_MUST_NOT_APPEAR' not in body


def test_new_provisioned_account_requires_confirmation_without_granting_approval(env):
    app, _, patients, *_ = env
    client = as_user(env, 'admin')
    response = client.post('/admin/users', data={'name': 'New Synthetic Nurse', 'email': 'new@example.test',
        'password': PASSWORD, 'role': 'nurse'})
    assert response.status_code == 302
    state = db.session.scalars(select(AccountVerification).where(
        AccountVerification.requested_email == 'new@example.test')).one()
    member = db.session.scalars(select(Membership).where(Membership.user_id == state.user_id)).one()
    assert member.role == 'nurse' and member.institution_id == patients[0].institution_id
    member.enabled = False
    db.session.commit()
    client = app.test_client()
    assert client.post('/auth/verify', data={'token': verify_token(state)}).status_code == 302
    assert not member.enabled and not jobs('welcome')
    admin = as_user(env, 'admin')
    assert admin.post(f'/admin/users/{member.id}/toggle').status_code == 302
    assert member.enabled and len(jobs('welcome')) == 1
    assert admin.post(f'/admin/users/{member.id}/toggle').status_code == 302
    assert admin.post(f'/admin/users/{member.id}/toggle').status_code == 302
    assert len(jobs('welcome')) == 1


def test_existing_staff_onboard_without_changing_memberships_and_cannot_skip_mfa(env):
    app, users, patients, *_ = env
    app.config.update(AUTH_REQUIRE_STAFF_MFA=True, AUTH_MFA_KEY=Fernet.generate_key())
    doctor = users['dr']
    target = f'/med/patients/{patients[0].id}/records/diagnoses'
    old_tab = as_user(env, 'dr')
    with old_tab.session_transaction() as signed:
        row = db.session.get(PortalSession, portal_sessions.digest(signed['portal_token']))
    row.mfa_at = portal_sessions.clock()
    db.session.commit()
    assert old_tab.get(target).status_code == 200
    db.session.delete(db.session.get(AccountVerification, doctor.id))
    db.session.commit()
    memberships = db.session.execute(select(Membership.id, Membership.role, Membership.enabled).where(
        Membership.user_id == doctor.id)).all()
    assert old_tab.get(target).status_code == 302
    client = app.test_client()
    client.post('/auth/verification', data={'email': doctor.email})
    assert not jobs('verify')
    assert password_login(client, 'dr').location.endswith('/auth/verification')
    assert client.get(target).status_code == 302
    provider = security_email.FakeMailProvider()
    assert security_email.deliver_pending(provider) == 1
    message = next(iter(provider.messages.values()))
    token = re.search(r'/auth/verify\?t=([A-Za-z0-9_.-]+)', message.body)[1]
    assert client.get('/auth/verify', query_string={'t': token}).status_code == 200
    assert client.get(target).status_code == 302
    assert client.post('/auth/verify', data={'token': token}).location.endswith('/auth/login')
    assert password_login(client, 'dr').location.endswith('/auth/mfa')
    pending = copy_cookie(app, client)
    assert client.get(target).status_code == 302
    secret = re.search(rb'<code>([A-Z2-7]+)</code>', client.get('/auth/mfa').data)[1].decode()
    assert b'Save your recovery codes' in client.post('/auth/mfa', data={'code': pyotp.TOTP(secret).now()}).data
    assert pending.get(target).status_code == 302
    assert client.get(target).status_code == 200
    assert client.get(f'/med/patients/{patients[2].id}/records/diagnoses').status_code == 404
    assert db.session.execute(select(Membership.id, Membership.role, Membership.enabled).where(
        Membership.user_id == doctor.id)).all() == memberships
    # Even the fixture-only switch cannot disable an already-enrolled factor.
    app.config['AUTH_REQUIRE_STAFF_MFA'] = False
    client.post('/auth/logout')
    assert password_login(client, 'dr').location.endswith('/auth/mfa')
    assert client.get(target).status_code == 302
    assert client.post('/auth/sso/begin').status_code == 404


def test_staff_mfa_disable_flag_is_rejected_outside_synthetic_mode():
    from app import create_app
    with pytest.raises(RuntimeError, match='mandatory'):
        create_app({'TESTING': False, 'AUTH_REQUIRE_STAFF_MFA': False,
                    'SQLALCHEMY_DATABASE_URI': 'sqlite://'})


def test_assisted_recovery_requires_two_scoped_admin_proofs_and_restores_access(env, monkeypatch):
    from models import AccountRecovery, AuditEvent, RecoveryCode, VerifiedPhone
    from portal_sessions import digest

    app, users, patients, *_ = env
    now = int(time.time())
    monkeypatch.setattr(multi_factor, 'clock', lambda: now)
    app.config['AUTH_MFA_KEY'] = key = Fernet.generate_key()
    target, requester, approver = (users[role] for role in ('patient', 'admin', 'dr2'))
    old = as_user(env, 'patient')
    institution = patients[0].institution_id
    codes = {}
    for user in (target, requester, approver):
        secret = pyotp.random_base32()
        db.session.add(Authenticator(user_id=user.id, encrypted_secret=Fernet(key).encrypt(secret.encode()),
                                    last_counter=0))
        codes[user.id] = pyotp.TOTP(secret).at(now)
    db.session.flush()
    db.session.add(RecoveryCode(user_id=target.id, code_hash=digest('synthetic-old-code')))
    db.session.add(VerifiedPhone(user_id=target.id, verified_at=now,
                                encrypted_number=Fernet(key).encrypt(b'+12025550123')))
    db.session.commit()
    runner = app.test_cli_runner()

    def invoke(approval, ticket, new_address=None, password=None):
        args = ['start-assisted-recovery', '--institution-id', str(institution), '--user-id', str(target.id),
                '--requestor-id', str(requester.id), '--approver-id', str(approval.id), '--ticket', ticket]
        input_data = f'{PASSWORD}\n{codes[requester.id]}\n{PASSWORD}\n{codes[approval.id]}\n'
        if password:
            args.append('--reset-password')
            input_data = f'{password}\n{password}\n' + input_data
        if new_address:
            args.append('--replacement-email')
            input_data = f'{new_address}\n{new_address}\n' + input_data
        return runner.invoke(args=args, input=input_data)

    assert invoke(requester, 'SAMPLE-001').exit_code == 1
    assert invoke(approver, 'SAMPLE-001').exit_code == 1  # Same institution, but still a doctor.
    assert db.session.get(Authenticator, target.id)
    assert db.session.get(AccountRecovery, 'SAMPLE-001') is None
    membership = db.session.scalar(select(Membership).where(Membership.user_id == approver.id))
    membership.role = 'admin'  # Explicit synthetic operator approval before recovery.
    db.session.commit()
    replacement_password = 'Synthetic replacement password'
    result = invoke(approver, 'SAMPLE-001', new_address='replacement@example.test',
                    password=replacement_password)
    assert result.exit_code == 0, result.exception
    assert PASSWORD not in result.output and 'replacement@example.test' not in result.output
    assert replacement_password not in result.output
    record = db.session.get(AccountRecovery, 'SAMPLE-001')
    assert (record.requestor_id, record.approver_id, record.user_id) == (requester.id, approver.id, target.id)
    assert set(db.session.scalars(select(AuditEvent.action).where(
        AuditEvent.resource_id == target.id, AuditEvent.action.like('assisted_recovery_%')))) == {
            'assisted_recovery_requested', 'assisted_recovery_approved', 'assisted_recovery_password_reset',
            'assisted_recovery_phone_revoked'}
    assert db.session.get(Authenticator, target.id) is None
    assert db.session.get(VerifiedPhone, target.id) is None
    assert not db.session.scalars(select(RecoveryCode).where(RecoveryCode.user_id == target.id)).all()
    assert old.get('/med/appointments').status_code == 302
    state = db.session.get(AccountVerification, target.id)
    assert state.mfa_reenroll_required and state.verified_at is None
    client = app.test_client()
    assert not target.check_password(PASSWORD)
    credentials = {'email': 'replacement@example.test', 'password': replacement_password}
    assert client.post('/auth/login', data=credentials).location.endswith('/auth/verification')
    assert client.post('/auth/verify', data={'token': verify_token(state)}).location.endswith('/auth/login')
    assert client.post('/auth/login', data=credentials).location.endswith('/auth/mfa')
    assert client.get('/med/appointments').status_code == 302
    secret = re.search(rb'<code>([A-Z2-7]+)</code>', client.get('/auth/mfa').data)[1].decode()
    assert b'Save your recovery codes' in client.post('/auth/mfa', data={'code': pyotp.TOTP(secret).at(now)}).data
    assert client.get('/med/appointments').status_code == 200
    assert client.get('/med/patients').status_code == 403
    assert not state.mfa_reenroll_required


@pytest.fixture
def oidc(env, monkeypatch):
    from authlib.integrations.flask_client import OAuth
    from joserfc import jwt
    from joserfc.jwk import RSAKey

    app = env[0]
    issuer = 'https://identity.example.test'
    audience = 'synthetic-portal'
    app.config.update(AUTH_SSO_ENABLED=True, AUTH_OIDC_ISSUER=issuer, AUTH_OIDC_CLIENT_ID=audience,
        AUTH_OIDC_REDIRECT_URI='https://portal.example.test/auth/sso/callback')
    remote = OAuth(app).register('synthetic_provider', client_id=audience, client_secret='synthetic-only',
                               client_kwargs={'scope': 'openid', 'code_challenge_method': 'S256'})
    metadata = {'issuer': issuer, 'authorization_endpoint': issuer + '/authorize',
                'token_endpoint': issuer + '/token', 'jwks_uri': issuer + '/jwks',
                'id_token_signing_alg_values_supported': ['RS256']}
    monkeypatch.setattr(remote, 'load_server_metadata', lambda: metadata)
    key = RSAKey.generate_key(2048, parameters={'kid': 'synthetic-key'})
    monkeypatch.setattr(remote, 'fetch_jwk_set', lambda **kwargs: {'keys': [key.as_dict()]})
    changes = {}
    seen = {}

    def exchange(**kwargs):
        assert kwargs['redirect_uri'] == app.config['AUTH_OIDC_REDIRECT_URI']
        assert re.fullmatch(r'[A-Za-z0-9._~-]{43,128}', kwargs['code_verifier'])
        now = int(time.time())
        claims = {'sub': 'stable-synthetic-subject', 'iss': issuer, 'aud': audience,
                  'iat': now, 'exp': now + 120, 'nonce': seen['nonce'], 'email': 'dr@example.test'}
        claims.update(changes)
        return {'id_token': jwt.encode({'alg': 'RS256', 'kid': 'synthetic-key'}, claims, key),
                'access_token': 'synthetic-unused-access-token'}

    monkeypatch.setattr(remote, 'fetch_access_token', exchange)
    app.extensions['portal_oidc'] = remote
    return changes, seen


def start_oidc(client, seen, *, link=False):
    data = {'action': 'link', 'password': PASSWORD} if link else {}
    result = client.post('/auth/sso/begin', data=data)
    assert result.status_code == 302
    params = parse_qs(urlsplit(result.headers['Location']).query)
    assert params['code_challenge_method'] == ['S256'] and params['code_challenge'][0]
    assert params['prompt'] == ['login']
    seen['nonce'] = params['nonce'][0]
    return params['state'][0]


@pytest.mark.parametrize('claim,value', [
    ('iss', 'https://wrong.example.test'), ('aud', 'wrong-client'), ('nonce', 'wrong-nonce'),
    ('exp', 1), ('aud', ['synthetic-portal', 'wrong-client']),
])
def test_oidc_rejects_invalid_signed_callback_claims(env, oidc, claim, value):
    changes, seen = oidc
    client = env[0].test_client()
    state = start_oidc(client, seen)
    changes[claim] = value
    response = client.get('/auth/sso/callback', query_string={'code': 'synthetic', 'state': state})
    assert response.headers['Location'].endswith('/auth/login')
    assert client.get('/med').status_code == 302


def test_oidc_state_replay_explicit_link_no_email_merge_and_local_mfa(env, oidc):
    from models import FederatedIdentity

    app = env[0]
    _, seen = oidc
    app.config['AUTH_SSO_ENABLED'] = False
    assert app.test_client().post('/auth/sso/begin').status_code == 404
    app.config['AUTH_SSO_ENABLED'] = True
    client = app.test_client()
    state = start_oidc(client, seen)
    copied = copy_cookie(app, client)
    assert client.get('/auth/sso/callback', query_string={'code': 'synthetic', 'state': 'wrong'}).headers[
        'Location'].endswith('/auth/login')
    query = {'code': 'synthetic', 'state': state}
    assert client.get('/auth/sso/callback', query_string=query).headers['Location'].endswith('/sso/confirm')
    assert copied.get('/auth/sso/callback', query_string=query).headers['Location'].endswith('/auth/login')
    assert client.post('/auth/sso/confirm').headers['Location'].endswith('/auth/login')
    assert db.session.scalar(select(FederatedIdentity)) is None

    client = as_user(env, 'dr')
    state = start_oidc(client, seen, link=True)
    assert client.get('/auth/sso/callback', query_string={'code': 'synthetic', 'state': state}).headers[
        'Location'].endswith('/sso/confirm')
    assert client.get('/auth/sso/confirm').status_code == 200
    assert db.session.scalar(select(FederatedIdentity)) is None
    old = copy_cookie(app, client)
    assert client.post('/auth/sso/confirm').headers['Location'].endswith('/auth/security')
    assert old.get('/med').status_code == 302
    assert db.session.scalar(select(FederatedIdentity)).user_id == env[1]['dr'].id
    assert client.post('/auth/logout').status_code == 302
    assert client.get('/med').status_code == 302

    app.config.update(AUTH_REQUIRE_STAFF_MFA=True, AUTH_MFA_KEY=Fernet.generate_key())
    state = start_oidc(client, seen)
    client.get('/auth/sso/callback', query_string={'code': 'synthetic', 'state': state})
    assert client.post('/auth/sso/confirm').headers['Location'].endswith('/auth/mfa')
    assert client.get('/med').status_code == 302
