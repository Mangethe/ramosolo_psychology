from functools import wraps
from flask import abort, g, session
from flask_login import current_user
from sqlalchemy import select, false
from extensions import db
from models import Membership, Patient, CareAssignment, AuditEvent, User


def membership_for_request():
    g.membership = None
    g.memberships = []
    if not current_user.is_authenticated:
        return
    g.memberships = list(db.session.scalars(select(Membership).where(
        Membership.user_id == current_user.id, Membership.enabled.is_(True))))
    selected = session.get('institution_id')
    g.membership = next((m for m in g.memberships if m.institution_id == selected), None)
    if not g.membership and g.memberships:
        g.membership = g.memberships[0]
        session['institution_id'] = g.membership.institution_id


def require_roles(*roles):
    def decorate(fn):
        @wraps(fn)
        def protected(*args, **kwargs):
            if not current_user.is_authenticated:
                from extensions import login_manager
                return login_manager.unauthorized()
            if not g.membership or g.membership.role not in roles:
                abort(403)
            if g.membership.institution.kind != 'medical':
                abort(403)
            return fn(*args, **kwargs)
        return protected
    return decorate


def patient_scope():
    if not g.membership or g.membership.institution.kind != 'medical':
        return select(Patient).where(false())
    m = g.membership
    query = select(Patient).where(Patient.institution_id == m.institution_id)
    if m.role == 'admin':
        return query
    if m.role == 'dr':
        return query.where(Patient.doctor_id == current_user.id)
    if m.role == 'dr_assist':
        doctor = db.session.scalar(select(Membership.id).join(User, User.id == Membership.user_id).where(
            Membership.user_id == m.supervising_doctor_id,
            Membership.institution_id == m.institution_id,
            Membership.role == 'dr', Membership.enabled.is_(True), User.enabled.is_(True)))
        return query.where(Patient.doctor_id == m.supervising_doctor_id) if doctor else query.where(false())
    if m.role == 'nurse':
        return query.where(Patient.id.in_(select(CareAssignment.patient_id).where(
            CareAssignment.nurse_id == current_user.id)))
    return query.where(Patient.user_id == current_user.id)


def accessible_patient(patient_id):
    patient = db.session.scalar(patient_scope().where(Patient.id == patient_id))
    if not patient:
        abort(404)
    return patient


def audit(action, resource, resource_id):
    db.session.add(AuditEvent(institution_id=g.membership.institution_id,
        actor_id=current_user.id, action=action, resource_type=resource, resource_id=resource_id))
