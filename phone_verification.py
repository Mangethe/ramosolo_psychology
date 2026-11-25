"""Session-bound phone ownership verification. SMS is never a portal login factor."""
import hashlib
import hmac
import ipaddress
import re
import secrets

import phonenumbers
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, request
from sqlalchemy import update

from account_verification import email_allowed
from delivery_limits import reserve
from extensions import db
from models import AuditEvent, DeliveryLimit, PhoneChallenge, PortalSession, ROLES, User, VerifiedPhone
from portal_sessions import clock, deadlines, privilege_stamp
from security_email import enqueue
from sms_delivery import FakeSMSProvider, ProviderUnavailable, TwilioVerifyProvider

PURPOSE = 'phone_ownership'


def csv_set(value):
    return {item.strip() for item in value.split(',') if item.strip()}


def enabled(membership):
    config = current_app.config
    return bool(membership and membership.institution.kind == 'medical' and
        config['SMS_PROVIDER'] in ('twilio-verify', 'fake') and
        (config['SMS_PROVIDER'] != 'fake' or current_app.testing) and config['SMS_POLICY_APPROVED'] and
        membership.role in csv_set(config['SMS_ELIGIBLE_ROLES']))


def settings():
    config = current_app.config
    regions = csv_set(config['SMS_ALLOWED_REGIONS'])
    roles = csv_set(config['SMS_ELIGIBLE_ROLES'])
    key = config['SMS_LIMIT_KEY']
    validity = config['SMS_PROVIDER_VALIDITY_SECONDS']
    if (not key or len(key) < 32 or not config['SMS_KEY'] or not regions
            or not regions <= phonenumbers.SUPPORTED_REGIONS or not roles or not roles <= set(ROLES)
            or not 1 <= config['SMS_DAILY_MAX'] <= 100 or not 300 <= validity <= 86400):
        raise ValueError('Complete the approved SMS policy and key configuration.')
    return Fernet(config['SMS_KEY']), regions, key.encode(), validity


def normalize(value, regions):
    try:
        number = phonenumbers.parse(value, None) if re.fullmatch(r'\+[0-9 .()-]{3,39}', value) else None
    except phonenumbers.NumberParseException:
        return None
    if (not number or number.extension or not phonenumbers.is_valid_number(number)
            or phonenumbers.region_code_for_number(number) not in regions):
        return None
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def mask(number):
    return '••• ' + number[-4:]


def get_provider():
    if current_app.config['SMS_PROVIDER'] == 'fake' and current_app.testing:
        if 'portal_fake_sms' not in current_app.extensions:
            current_app.extensions['portal_fake_sms'] = FakeSMSProvider(
                clock, current_app.config['SMS_PROVIDER_VALIDITY_SECONDS'])
        return current_app.extensions['portal_fake_sms']
    return TwilioVerifyProvider(current_app.config)


def unseal(cipher, value):
    try:
        return cipher.decrypt(value).decode('ascii')
    except InvalidToken:
        raise ValueError('Phone verification state is unavailable.') from None


def masked_phone(cipher, row):
    return mask(unseal(cipher, row.encrypted_number)) if row else None


def key_for(secret, purpose, value):
    return hmac.new(secret, f'{purpose}:{value}'.encode(), hashlib.sha256).hexdigest()


def current(row, portal, institution_id):
    return (row and row.institution_id == institution_id and row.session_hash == portal.token_hash and
            row.purpose == PURPOSE and row.provider == current_app.config['SMS_PROVIDER']
            and row.expires_at > clock())


def send_buckets(user_id, destination, key, old=None):
    remote = str(ipaddress.ip_address(request.remote_addr or 'invalid'))
    client_key = key_for(key, 'ip', remote)
    maximum = current_app.config['SMS_DAILY_MAX']
    buckets = []
    for number in filter(None, (destination, old)):
        buckets.extend((('sms:global', 86400, maximum), (f'sms:user:{user_id}', 86400, 6),
            ('sms:ip:' + client_key, 3600, 12),
            ('sms:to:' + key_for(key, 'number', number), 86400, 4)))
    return buckets


def mark(row_id, from_state, **values):
    return db.session.execute(update(PhoneChallenge).where(PhoneChallenge.challenge_id == row_id,
        PhoneChallenge.state == from_state).values(**values)).rowcount == 1


def available_session(portal_hash, user_id, *, lock=False):
    portal = db.session.get(PortalSession, portal_hash, with_for_update=lock, populate_existing=True)
    user = db.session.get(User, user_id)
    return bool(portal and user and user.enabled and portal.user_id == user_id
        and user.session_version == portal.account_version and portal.privileges == privilege_stamp(user_id)
        and email_allowed(user) and deadlines(portal)[0] > clock())


def send(user, portal, institution_id, provider, config, *, submitted=None, challenge_id=None):
    cipher, regions, key, validity = config
    user_id, portal_hash = user.id, portal.token_hash
    now = clock()
    row = db.session.get(PhoneChallenge, user_id, with_for_update=True, populate_existing=True)
    old = None
    if submitted is not None:
        if row and row.expires_at > now and row.state != 'consumed':
            return 'hold'
        phone = db.session.get(VerifiedPhone, user_id)
        old = unseal(cipher, phone.encrypted_number) if phone else None
        destination = normalize(submitted.strip(), regions)
        if not destination or destination == old or (old and not normalize(old, regions)):
            return 'rejected'
        destination_key = key_for(key, 'number', destination)
        lease = ('sms:lease:' + destination_key, validity + 30, 1)
        if not reserve(now, lease, *send_buckets(user_id, destination, key, old)):
            return 'hold'
        if row is None:
            row = PhoneChallenge(user_id=user_id)
            db.session.add(row)
        row.challenge_id = secrets.token_urlsafe(32)
        row.institution_id = institution_id
        row.purpose = PURPOSE
        row.session_hash = portal_hash
        row.encrypted_number = cipher.encrypt(destination.encode('ascii'))
        row.destination_key = destination_key
        row.reference = None
        row.provider = current_app.config['SMS_PROVIDER']
        row.expires_at = min(now + 300, deadlines(portal)[0])
        row.attempts = 0
        row.sends = 1
        row.resend_after = now + 60
        row.state = 'sending'
        row_id = row.challenge_id
    else:
        if (not current(row, portal, institution_id) or row.challenge_id != challenge_id
                or row.state != 'pending' or now < row.resend_after or row.sends >= 3 or row.attempts >= 5):
            return 'hold'
        destination = unseal(cipher, row.encrypted_number)
        if not normalize(destination, regions) or not reserve(now, *send_buckets(user_id, destination, key)):
            return 'hold'
        row_id = row.challenge_id
        if not mark(row_id, 'pending', state='sending', sends=PhoneChallenge.sends + 1,
                    resend_after=now + 60 * row.sends):
            return 'hold'
        db.session.execute(update(DeliveryLimit).where(DeliveryLimit.key == 'sms:lease:' + row.destination_key,
            DeliveryLimit.expires_at > now).values(expires_at=now + validity + 30))
    if not available_session(portal_hash, user_id):
        return 'rejected'
    # Count even an ambiguous provider result against the spend cap.
    db.session.commit()
    try:
        if old:
            provider.notify_change(old)
        reference = provider.send(destination)
        state = 'pending'
    except (ProviderUnavailable, ValueError):
        reference, state = None, 'failed'
    mark(row_id, 'sending', state=state, reference=reference)
    db.session.commit()
    return 'sent' if state == 'pending' else 'unavailable'


def check(user_id, portal, institution_id, provider, config, challenge_id, code):
    if not re.fullmatch(r'[0-9]{4,10}', code):
        return False
    cipher, regions, _, _ = config
    portal_hash = portal.token_hash
    row = db.session.get(PhoneChallenge, user_id)
    if (not current(row, portal, institution_id) or row.challenge_id != challenge_id
            or row.state != 'pending' or not row.reference or row.attempts >= 5):
        return False
    destination = unseal(cipher, row.encrypted_number)
    reference = row.reference
    if not normalize(destination, regions) or not mark(challenge_id, 'pending', state='checking',
                                                       attempts=PhoneChallenge.attempts + 1):
        return False
    db.session.commit()  # A concurrent POST can no longer invoke the provider.
    try:
        approved = provider.check(reference, destination, code) is True
    except (ProviderUnavailable, ValueError):
        mark(challenge_id, 'checking', state='failed')
        db.session.commit()
        return False
    user = db.session.get(User, user_id, with_for_update=True, populate_existing=True)
    row = db.session.get(PhoneChallenge, user_id, with_for_update=True, populate_existing=True)
    if (not user or not row or row.challenge_id != challenge_id or row.state != 'checking'
            or row.expires_at <= clock() or not available_session(portal_hash, user_id, lock=True)):
        db.session.rollback()
        return False
    if not approved:
        row.state = 'failed' if row.attempts >= 5 else 'pending'
        db.session.commit()
        return False
    phone = db.session.get(VerifiedPhone, user_id)
    if not phone:
        phone = VerifiedPhone(user_id=user_id)
        db.session.add(phone)
    phone.encrypted_number = row.encrypted_number
    phone.verified_at = clock()
    row.state = 'consumed'
    user.session_version += 1
    db.session.add(AuditEvent(institution_id=institution_id, actor_id=user_id, action='verify_account_phone',
                               resource_type='user', resource_id=user_id))
    enqueue(user, 'change', 'phone:' + challenge_id, detail='Your verified account phone was updated.')
    db.session.commit()
    return True
