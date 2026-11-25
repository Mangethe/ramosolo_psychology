"""Dual-control recovery for medical accounts."""
import re

from sqlalchemy import delete, select

from account_verification import email_allowed, issue, valid_address
from extensions import db
from medical_services import utcnow
from models import (AccountRecovery, AccountVerification, AuditEvent, Authenticator, FederatedIdentity,
                    Institution, Membership, PendingAuthentication, PhoneChallenge, PortalSession, User,
                    VerifiedPhone)
from multi_factor import factor_proof
from portal_sessions import clock
from security_email import enqueue


def start_recovery(institution_id, user_id, ticket, approvals, *, replacement_email=None, new_password=None):
    requestor, approver = approvals
    identities = {user_id, requestor[0], approver[0]}
    if len(identities) != 3 or not re.fullmatch(r'[A-Z0-9][A-Z0-9-]{5,63}', ticket):
        return False
    if new_password is not None and not 12 <= len(new_password) <= 128:
        return False
    users = {user.id: user for user in db.session.scalars(select(User).where(
        User.id.in_(identities)).order_by(User.id).with_for_update().execution_options(populate_existing=True))}
    institution = db.session.get(Institution, institution_id)
    if (len(users) != 3 or any(not user.enabled for user in users.values()) or
            not institution or institution.kind != 'medical' or db.session.get(AccountRecovery, ticket)):
        return False
    target = users[user_id]
    previous_email = target.email
    if replacement_email is not None:
        replacement_email = replacement_email.strip().lower()
        if (not valid_address(replacement_email) or replacement_email == previous_email or
            db.session.scalar(select(User.id).where(User.email == replacement_email)) is not None):
            return False
    roles = list(db.session.scalars(select(Membership).where(Membership.user_id.in_(identities))))
    if ([member.institution_id for member in roles if member.user_id == user_id] != [institution_id]
            or not any(member.user_id == user_id and member.enabled for member in roles)):
        return False
    admins = {member.user_id for member in roles if member.institution_id == institution_id and
              member.enabled and member.role == 'admin'}
    factors = {factor.user_id: factor for factor in db.session.scalars(select(Authenticator).where(
        Authenticator.user_id.in_(identities)).order_by(Authenticator.user_id).with_for_update())}
    target_factor = factors.get(user_id)
    now = utcnow()
    if ((replacement_email is None and (not (target_factor or new_password) or not email_allowed(target))) or
            any(identity not in admins or not email_allowed(users[identity]) or
                identity not in factors or
                (users[identity].locked_until and users[identity].locked_until > now) or
                not 1 <= len(password) <= 512 or not users[identity].check_password(password)
                for identity, password, _ in approvals)):
        return False
    proofs = [factor_proof(factors[identity], code, allow_recovery=False)
              for identity, _, code in approvals]
    if proofs != ['totp', 'totp']:
        db.session.commit()  # Keep the ordinary account factor rate limits.
        return False
    if not issue(target, replacement_email or previous_email, initial=replacement_email is not None):
        db.session.rollback()
        return False
    state = db.session.get(AccountVerification, user_id)
    state.verified_email = None
    state.verified_at = None
    state.mfa_reenroll_required = bool(target_factor or state.mfa_reenroll_required)
    if replacement_email:
        target.email = replacement_email
    if new_password is not None:
        target.set_password(new_password)
        target.failed_logins = 0
        target.locked_until = None
    else:
        target.session_version += 1
    if target_factor:
        db.session.delete(target_factor)  # Recovery codes cascade.
    for model in (PortalSession, PendingAuthentication, FederatedIdentity, PhoneChallenge):
        db.session.execute(delete(model).where(model.user_id == user_id))
    revoked_phone = db.session.execute(delete(VerifiedPhone).where(VerifiedPhone.user_id == user_id)).rowcount
    db.session.add(AccountRecovery(ticket=ticket, institution_id=institution_id, user_id=user_id,
        requestor_id=requestor[0], approver_id=approver[0], started_at=clock()))
    db.session.add_all(AuditEvent(institution_id=institution_id, actor_id=actor[0], action=action,
        resource_type='user', resource_id=user_id) for actor, action in zip(approvals,
            ('assisted_recovery_requested', 'assisted_recovery_approved')))
    if new_password is not None:
        db.session.add(AuditEvent(institution_id=institution_id, actor_id=approver[0],
            action='assisted_recovery_password_reset', resource_type='user', resource_id=user_id))
    if revoked_phone:
        db.session.add(AuditEvent(institution_id=institution_id, actor_id=approver[0],
            action='assisted_recovery_phone_revoked', resource_type='user', resource_id=user_id))
    if valid_address(previous_email):
        enqueue(target, 'change', f'recovery-start:{user_id}:{target.session_version}', recipient=previous_email,
                detail='The practice approved account recovery. Contact support if this was unexpected.')
    db.session.commit()
    return True
