"""Server-side authentication and activity deadlines for signed browser cookies."""
import hashlib
import secrets
import time

from flask import current_app, g, session
from flask_login import login_user, logout_user
from sqlalchemy import delete, select, update

from extensions import db
from models import Authenticator, Institution, Membership, PendingAuthentication, PortalSession, User


def clock():
    return int(time.time())


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def privilege_stamp(user_id):
    rows = db.session.execute(select(Membership.institution_id, Membership.role,
        Membership.supervising_doctor_id, Institution.kind).join(Institution).where(
        Membership.user_id == user_id, Membership.enabled.is_(True)).order_by(Membership.institution_id))
    return digest(repr([tuple(row) for row in rows]))


def idle_seconds():
    return int(current_app.config['AUTH_IDLE_TIMEOUT'].total_seconds())


def create_session(user, *, started_at=None, absolute_at=None, mfa_at=None, mfa_method=None):
    token = secrets.token_urlsafe(32)
    now = clock()
    db.session.add(PortalSession(token_hash=digest(token), user_id=user.id, account_version=user.session_version,
        privileges=privilege_stamp(user.id), started_at=now if started_at is None else started_at,
        last_seen_at=now, idle_expires_at=now + idle_seconds(),
        absolute_expires_at=absolute_at if absolute_at is not None else
        now + int(current_app.config['PERMANENT_SESSION_LIFETIME'].total_seconds()),
        mfa_at=mfa_at, mfa_method=mfa_method))
    return token


def activate_session(user, token):
    session.clear()
    login_user(user, remember=False)
    session['portal_token'] = token
    session['_remember'] = 'clear'
    session.permanent = True
    g.portal_session = db.session.get(PortalSession, digest(token))


def deadlines(row):
    return min(row.absolute_expires_at, row.idle_expires_at), row.absolute_expires_at


def load_session(user_identity):
    token = session.get('portal_token')
    if not isinstance(token, str) or len(token) != 43:
        return None
    row = db.session.get(PortalSession, digest(token), populate_existing=True)
    now = clock()
    if not row or now >= deadlines(row)[0] or not row.started_at <= row.last_seen_at <= now:
        return None
    user = db.session.get(User, row.user_id, populate_existing=True)
    if (not user or not user.enabled or user.get_id() != user_identity or
            user.session_version != row.account_version or privilege_stamp(user.id) != row.privileges):
        return None
    from account_verification import email_allowed
    if not email_allowed(user):
        return None
    from multi_factor import requires_mfa
    if row.mfa_at is None and (requires_mfa(user.id) or db.session.get(Authenticator, user.id)):
        return None
    g.portal_session = row
    return user


def rotate(user, institution_id):
    row = g.portal_session
    # Claim the old identifier before creating a replacement. A concurrent
    # logout or another rotation cannot turn a revoked cookie into a new session.
    claimed = db.session.execute(delete(PortalSession).where(
        PortalSession.token_hash == row.token_hash, PortalSession.absolute_expires_at > clock(),
        PortalSession.idle_expires_at > clock())).rowcount
    if claimed != 1:
        db.session.rollback()
        return False
    token = create_session(user, started_at=row.started_at, absolute_at=row.absolute_expires_at,
                           mfa_at=row.mfa_at, mfa_method=row.mfa_method)
    db.session.commit()
    activate_session(user, token)
    session['institution_id'] = institution_id
    return True


def extend(row):
    now = clock()
    if now >= deadlines(row)[0]:
        return False
    result = db.session.execute(update(PortalSession).where(PortalSession.token_hash == row.token_hash,
        PortalSession.idle_expires_at > now, PortalSession.absolute_expires_at > now,
        PortalSession.last_seen_at <= now).values(last_seen_at=now, idle_expires_at=now + idle_seconds()))
    updated = result.rowcount == 1
    db.session.commit()
    return updated


def sign_out():
    row = getattr(g, 'portal_session', None)
    if row is not None:
        db.session.execute(delete(PortalSession).where(PortalSession.token_hash == row.token_hash))
    pending = session.get('mfa_pending')
    if isinstance(pending, str) and len(pending) == 43:
        db.session.execute(delete(PendingAuthentication).where(PendingAuthentication.token_hash == digest(pending)))
    if 'sso_exchange' in session:
        from sso import clear_exchange
        clear_exchange()
    db.session.commit()
    logout_user()
    session.clear()
    session['_remember'] = 'clear'


def page_identity(row):
    return digest('ramosolo:page:' + row.token_hash)[:24]
