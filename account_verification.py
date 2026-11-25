"""Email verification for provisioned accounts, independent of role approval."""
import hashlib
import hmac
import re
import secrets

from flask import current_app
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import AccountVerification, Institution, Membership, SecurityEmail, User
from portal_sessions import clock, digest
from security_email import enqueue


def email_allowed(user):
    state = db.session.get(AccountVerification, user.id, populate_existing=True)
    if state is not None:
        return state.verified_at is not None and state.verified_email == user.email
    return db.session.scalar(select(Membership.id).join(Institution).where(
        Membership.user_id == user.id, Institution.kind == 'medical').limit(1)) is None


def valid_address(email):
    return bool(len(email) <= 254 and re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', email))


def verification_token(identifier, user_id, email):
    key = current_app.config['AUTH_VERIFICATION_KEY'] or current_app.secret_key
    payload = f'ramosolo:verify-email:{identifier}:{user_id}:{email}'.encode()
    return identifier + '.' + hmac.new(key.encode() if isinstance(key, str) else key, payload, hashlib.sha256).hexdigest()


def issue(user, address, *, initial=False):
    state = db.session.get(AccountVerification, user.id, with_for_update=True, populate_existing=True)
    if state is None:
        if not initial:
            return False
        state = AccountVerification(user_id=user.id, resend_after=0, window_started_at=0, send_count=0)
        db.session.add(state)
    now = clock()
    if now < state.resend_after:
        return False
    if now >= state.window_started_at + 3600:
        state.window_started_at = now
        state.send_count = 0
    if state.send_count >= 3:
        return False
    state.requested_email = address
    state.verification_id = secrets.token_urlsafe(32)
    state.token_hash = digest(verification_token(state.verification_id, user.id, address))
    state.expires_at = now + current_app.config['AUTH_VERIFICATION_SECONDS']
    state.resend_after = now + 60
    state.send_count += 1
    enqueue(user, 'verify', 'verify:' + state.verification_id, detail=state.verification_id, recipient=address)
    return True


def welcome_if_active(user):
    state = db.session.get(AccountVerification, user.id)
    if not state or state.verified_email != user.email or not user.enabled:
        return
    active = db.session.scalar(select(Membership.id).join(Institution).where(
        Membership.user_id == user.id, Membership.enabled.is_(True),
        Institution.kind == 'medical').limit(1))
    key = f'welcome:{user.id}'
    if active and db.session.get(SecurityEmail, key) is None:
        enqueue(user, 'welcome', key)


def confirm(token):
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}\.[a-f0-9]{64}', token):
        return False
    identifier = token.split('.')[0]
    user_id = db.session.scalar(select(AccountVerification.user_id).where(
        AccountVerification.verification_id == identifier))
    if user_id is None:
        return False
    user = db.session.get(User, user_id, with_for_update=True, populate_existing=True)
    state = db.session.get(AccountVerification, user_id, with_for_update=True, populate_existing=True)
    now = clock()
    if (not user or not user.enabled or not state or state.verification_id != identifier or
            state.expires_at <= now or not hmac.compare_digest(state.token_hash, digest(token))):
        return False
    address = state.requested_email
    try:
        changed = db.session.execute(update(AccountVerification).where(
            AccountVerification.user_id == user_id, AccountVerification.verification_id == identifier,
            AccountVerification.token_hash == digest(token), AccountVerification.expires_at > now
        ).values(verified_email=address, verified_at=now, verification_id=None, token_hash=None,
                 expires_at=None, requested_email=None)).rowcount
        if changed != 1:
            db.session.rollback()
            return False
        if user.email != address:
            previous_email = user.email
            user.email = address
            user.session_version += 1
            enqueue(user, 'change', 'email-old:' + identifier, recipient=previous_email,
                    detail='The sign-in email address changed.')
            enqueue(user, 'change', 'email-new:' + identifier, detail='The sign-in email address changed.')
        welcome_if_active(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return False
    return True
