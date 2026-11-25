"""Single-provider OpenID Connect entry point for explicitly linked accounts."""
import hmac
import re
import secrets
from urllib.parse import urlsplit

from authlib.integrations.flask_client import OAuth
from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, session, url_for
from flask_login import current_user
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from auth import begin_login, reauthenticate
from extensions import db
from models import AccountVerification, Authenticator, FederatedIdentity, OIDCExchange, User
from portal_sessions import clock, digest, rotate
from security_email import enqueue, trusted_origin


bp = Blueprint('sso', __name__, url_prefix='/auth/sso')
CALLBACK_PATH = '/auth/sso/callback'


def https_url(value):
    parsed = urlsplit(value or '')
    return bool(parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password
                and not parsed.query and not parsed.fragment and '\\' not in value
                and not any(character.isspace() for character in value))


def register_sso(app):
    app.register_blueprint(bp)
    if not app.config['AUTH_SSO_ENABLED']:
        return
    issuer = app.config['AUTH_OIDC_ISSUER']
    callback = trusted_origin(app.config['AUTH_PUBLIC_URL'], https_only=True) + CALLBACK_PATH
    if (not https_url(issuer) or len(issuer) > 350 or issuer.endswith('/') or
            app.config['AUTH_OIDC_REDIRECT_URI'] != callback or
            not app.config['AUTH_OIDC_CLIENT_ID'] or not app.config['AUTH_OIDC_CLIENT_SECRET']):
        raise RuntimeError('Configure the OIDC issuer, client credentials and exact HTTPS callback.')
    oauth = OAuth(app)
    app.extensions['portal_oidc'] = oauth.register('portal_provider',
        client_id=app.config['AUTH_OIDC_CLIENT_ID'], client_secret=app.config['AUTH_OIDC_CLIENT_SECRET'],
        server_metadata_url=issuer + '/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid', 'code_challenge_method': 'S256'})


@bp.before_request
def enabled():
    if not current_app.config['AUTH_SSO_ENABLED']:
        abort(404)


def provider():
    remote = current_app.extensions['portal_oidc']
    metadata = remote.load_server_metadata()
    if (metadata.get('issuer') != current_app.config['AUTH_OIDC_ISSUER'] or
            any(not https_url(metadata.get(name)) for name in
                ('authorization_endpoint', 'token_endpoint', 'jwks_uri')) or
            'RS256' not in metadata.get('id_token_signing_alg_values_supported', ())):
        raise ValueError('Unexpected OIDC metadata.')
    metadata['id_token_signing_alg_values_supported'] = ['RS256']
    return remote


def failure():
    current_app.logger.warning('OIDC authentication was not completed')
    flash('Identity provider sign-in could not be completed.', 'error')
    return redirect(url_for('auth.login'))


def clear_exchange():
    token = session.pop('sso_exchange', None)
    if isinstance(token, str) and re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        db.session.execute(delete(OIDCExchange).where(OIDCExchange.token_hash == digest(token)))


@bp.post('/begin')
def begin():
    link = request.form.get('action') == 'link'
    if link != current_user.is_authenticated:
        abort(403)
    portal = getattr(g, 'portal_session', None)
    if link:
        user = db.session.get(User, current_user.id, with_for_update=True, populate_existing=True)
        factor = db.session.get(Authenticator, user.id, with_for_update=True)
        if not user or user.get_id() != session.get('_user_id') or not reauthenticate(user, factor):
            return failure()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    try:
        authorization = provider().create_authorization_url(current_app.config['AUTH_OIDC_REDIRECT_URI'],
            state=state, nonce=nonce, prompt='login')
        verifier = authorization['code_verifier']
    except Exception:
        db.session.rollback()
        return failure()
    clear_exchange()
    db.session.add(OIDCExchange(token_hash=digest(state), expires_at=clock() + 300,
        session_hash=portal.token_hash if link else None, issuer=current_app.config['AUTH_OIDC_ISSUER'],
        code_verifier=verifier, nonce=nonce))
    db.session.commit()
    session['sso_exchange'] = state
    return redirect(authorization['url'])


def consume_exchange(*, proof=False):
    token = session.pop('sso_exchange', None)
    if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        return None
    row = db.session.execute(delete(OIDCExchange).where(OIDCExchange.token_hash == digest(token))
        .returning(OIDCExchange.expires_at, OIDCExchange.session_hash, OIDCExchange.code_verifier,
                   OIDCExchange.nonce, OIDCExchange.issuer, OIDCExchange.subject)).first()
    db.session.commit()
    portal = getattr(g, 'portal_session', None)
    if (not row or row.expires_at <= clock() or row.issuer != current_app.config['AUTH_OIDC_ISSUER'] or
            row.session_hash != (portal.token_hash if portal else None) or bool(row.subject) != proof):
        return None
    return row


@bp.get('/callback')
def callback():
    state = request.args.get('state', '')
    cookie = session.get('sso_exchange')
    if (not isinstance(cookie, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', state)
            or not hmac.compare_digest(cookie, state)):
        return failure()
    row = consume_exchange()
    code = request.args.get('code', '')
    if row is None or not 1 <= len(code) <= 4096 or request.args.get('error'):
        return failure()
    issuer = current_app.config['AUTH_OIDC_ISSUER']
    client_id = current_app.config['AUTH_OIDC_CLIENT_ID']
    if request.args.get('iss', issuer) != issuer:
        return failure()
    try:
        remote = provider()
        token = remote.fetch_access_token(redirect_uri=current_app.config['AUTH_OIDC_REDIRECT_URI'],
                                         code=code, code_verifier=row.code_verifier)
        claims = remote.parse_id_token(token, nonce=row.nonce,
            claims_options={'iss': {'essential': True, 'value': issuer}}, leeway=30)
    except Exception:
        return failure()
    aud = claims.get('aud', []) if claims else []
    audiences = [aud] if isinstance(aud, str) else aud
    subject = claims.get('sub') if claims else None
    if (not claims or claims.get('iss') != issuer or claims.get('nonce') != row.nonce or
            not isinstance(audiences, list) or client_id not in audiences or
            claims.get('azp', client_id) != client_id or (len(audiences) > 1 and claims.get('azp') != client_id) or
            not isinstance(subject, str) or not 1 <= len(subject) <= 255):
        return failure()
    proof = secrets.token_urlsafe(32)
    db.session.add(OIDCExchange(token_hash=digest(proof), expires_at=clock() + 120,
        session_hash=row.session_hash, issuer=issuer, subject=subject))
    db.session.commit()
    session['sso_exchange'] = proof
    return redirect(url_for('sso.confirm'))


@bp.route('/confirm', methods=['GET', 'POST'])
def confirm():
    if request.method == 'GET':
        return render_template('auth/sso_confirm.html', linking=current_user.is_authenticated)
    row = consume_exchange(proof=True)
    if row is None:
        return failure()
    identity = db.session.get(FederatedIdentity, (row.issuer, row.subject))
    if row.session_hash:
        if identity is not None:
            return failure()
        user = db.session.get(User, current_user.id, with_for_update=True, populate_existing=True)
        if not user.enabled or user.get_id() != session.get('_user_id'):
            return failure()
        db.session.add(FederatedIdentity(issuer=row.issuer, subject=row.subject, user_id=user.id))
        user.session_version += 1
        enqueue(user, 'change', 'sso:' + digest(row.issuer + '\n' + row.subject),
                detail='An identity provider was linked.')
        try:
            if not rotate(user, session.get('institution_id')):
                return failure()
        except IntegrityError:
            db.session.rollback()
            return failure()
        flash('Identity provider linked.', 'success')
        return redirect(url_for('auth.security_settings'))
    if identity is None:
        return failure()
    user = db.session.get(User, identity.user_id, with_for_update=True, populate_existing=True)
    if not user:
        return failure()
    state = db.session.get(AccountVerification, user.id)
    if state and state.mfa_reenroll_required:
        return failure()
    return begin_login(user)
