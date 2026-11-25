"""TOTP enrolment, replay prevention, and recovery for local accounts."""
import re
import secrets
from datetime import datetime, timezone

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, session
from sqlalchemy import delete, select, update

from account_verification import email_allowed
from extensions import db
from models import AccountVerification, Authenticator, Institution, Membership, PendingAuthentication, RecoveryCode, User
from portal_sessions import clock, digest, privilege_stamp


def staff_requires_mfa(user_id):
    return current_app.config['AUTH_REQUIRE_STAFF_MFA'] and db.session.scalar(select(Membership.id)
        .join(Institution).where(Membership.user_id == user_id, Membership.enabled.is_(True),
        Membership.role != 'patient', Institution.kind == 'medical').limit(1)) is not None


def requires_mfa(user_id):
    state = db.session.get(AccountVerification, user_id)
    return bool((state and state.mfa_reenroll_required) or staff_requires_mfa(user_id))


def key_cipher():
    key = current_app.config.get('AUTH_MFA_KEY')
    try:
        return Fernet(key) if key else None
    except (TypeError, ValueError):
        return None


def read_secret(encrypted):
    cipher = key_cipher()
    if cipher is not None:
        try:
            return cipher.decrypt(encrypted).decode('ascii')
        except InvalidToken:
            return None
    return None


def start(user, mode):
    cipher = key_cipher()
    if not cipher:
        return None
    token = secrets.token_urlsafe(32)
    db.session.execute(delete(PendingAuthentication).where(PendingAuthentication.user_id == user.id))
    secret = cipher.encrypt(pyotp.random_base32().encode('ascii')) if mode != 'challenge' else None
    db.session.add(PendingAuthentication(token_hash=digest(token), user_id=user.id,
        account_version=user.session_version, privileges=privilege_stamp(user.id), expires_at=clock() + 300,
        mode=mode, encrypted_secret=secret))
    return token


def pending(*, lock=False):
    token = session.get('mfa_pending')
    if not isinstance(token, str) or len(token) != 43:
        return None, None
    token_hash = digest(token)
    row = db.session.get(PendingAuthentication, token_hash)
    if row is None:
        return None, None
    user = db.session.get(User, row.user_id, with_for_update=lock, populate_existing=True)
    row = db.session.get(PendingAuthentication, token_hash, with_for_update=lock, populate_existing=True)
    if (not row or row.expires_at <= clock() or row.attempts >= 5 or not user or not user.enabled
            or user.session_version != row.account_version or privilege_stamp(user.id) != row.privileges
            or not email_allowed(user)):
        return None, None
    return user, row


def counter_for(secret, code):
    if secret is None or not re.fullmatch(r'[0-9]{6}', code):
        return None
    now = clock()
    totp = pyotp.TOTP(secret)
    instant = datetime.fromtimestamp(now, timezone.utc)
    return now // totp.interval if totp.verify(code, for_time=instant) else None


def factor_proof(factor, code, *, allow_recovery):
    now = clock()
    if factor.blocked_until > now:
        return None
    counter = counter_for(read_secret(factor.encrypted_secret), code)
    if counter is not None and counter > factor.last_counter:
        consumed = db.session.execute(update(Authenticator).where(Authenticator.user_id == factor.user_id,
            Authenticator.last_counter < counter).values(last_counter=counter, attempts=0, blocked_until=0))
        if consumed.rowcount == 1:
            return 'totp'
    if allow_recovery and re.fullmatch(r'[A-Za-z0-9_-]{22}', code):
        consumed = db.session.execute(delete(RecoveryCode).where(RecoveryCode.user_id == factor.user_id,
            RecoveryCode.code_hash == digest(code)))
        if consumed.rowcount == 1:
            factor.attempts = factor.blocked_until = 0
            return 'recovery'
    factor.attempts += 1
    if factor.attempts >= 5:
        factor.attempts = 0
        factor.blocked_until = now + 300
    return None


def register_factor(user, row, counter):
    factor = db.session.get(Authenticator, user.id, with_for_update=True)
    if factor:
        db.session.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
        factor.encrypted_secret = row.encrypted_secret
        factor.last_counter = counter
        factor.attempts = factor.blocked_until = 0
    else:
        db.session.add(Authenticator(user_id=user.id, encrypted_secret=row.encrypted_secret, last_counter=counter))
        db.session.flush()
    codes = [secrets.token_urlsafe(16) for _ in range(10)]
    db.session.add_all(RecoveryCode(user_id=user.id, code_hash=digest(code)) for code in codes)
    return codes
