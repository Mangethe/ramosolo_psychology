from functools import wraps
from flask import abort, g, session
from flask_login import current_user
from sqlalchemy import select, false
from extensions import db
from models import Appointment, Membership, Patient, CareAssignment, AuditEvent, User, PatientPermission

# Executable matrix. A possible capability still requires the patient/query scope below.
READ_PERMISSIONS = {
    'care_plan': 'Agreed care information', 'clinical_events': 'Clinician-recorded clinical events',
    'patient_concerns': 'Patient-reported concerns', 'diagnoses': 'Clinician-authored diagnoses',
    'clinical_notes': 'Clinical notes', 'psychotherapy_notes': 'Psychotherapy notes',
    'observations': 'Nursing observations', 'external_practitioners': 'External treating practitioners',
    'export': 'Patient-specific export authorization',
}
ROLE_MATRIX = {
    'dr': {'operational', 'schedule', 'administrative_followup', 'admissions', 'operational_totals',
           'clinical_read', 'clinical_author', 'grant_access', 'export'},
    'nurse': {'operational', 'admissions', 'operational_totals', 'clinical_read', 'observe', 'assigned_tasks'},
    'dr_assist': {'operational', 'schedule', 'operational_totals', 'administrative_followup'},
    'patient': {'own_appointments', 'patient_plan', 'check_in', 'preferences'},
    'admin': {'operational', 'schedule', 'administrative_followup', 'admissions', 'accounts', 'institution_configuration', 'facilities',
              'operational_totals', 'clinical_read', 'export'},
}
DELEGABLE = {
    'admin': set(READ_PERMISSIONS),
    'nurse': set(READ_PERMISSIONS) - {'psychotherapy_notes', 'export'},
}


def capability(name):
    m = getattr(g, 'membership', None)
    return bool(m and m.institution.kind == 'medical' and name in ROLE_MATRIX.get(m.role, set()))


def require_capability(name):
    def decorate(fn):
        @wraps(fn)
        @require_roles(*ROLE_MATRIX)
        def protected(*args, **kwargs):
            if not capability(name):
                abort(403)
            return fn(*args, **kwargs)
        return protected
    return decorate


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


def operational_patient_scope():
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
    if m.role == 'patient':
        return query.where(Patient.user_id == current_user.id)
    return query.where(false())


def patient_scope(permission='operational'):
    query = operational_patient_scope()
    if permission == 'operational':
        return query
    m = getattr(g, 'membership', None)
    if permission not in READ_PERMISSIONS or not m:
        return query.where(false())
    if m.role == 'dr':
        return query  # assigned clinician, never another doctor's cohort
    if permission not in DELEGABLE.get(m.role, set()):
        return query.where(false())
    # Grants are bound to the active membership, institution, current treating doctor,
    # and (for nurses) a still-active care assignment through operational scope.
    approver = select(Membership.user_id).join(User, User.id == Membership.user_id).where(
        Membership.institution_id == m.institution_id, Membership.role == 'dr',
        Membership.enabled.is_(True), User.enabled.is_(True))
    permitted = select(PatientPermission.patient_id).join(Patient, Patient.id == PatientPermission.patient_id).where(
        PatientPermission.institution_id == m.institution_id,
        Patient.institution_id == m.institution_id, PatientPermission.membership_id == m.id,
        PatientPermission.permission == permission, PatientPermission.enabled.is_(True),
        PatientPermission.approved_by_id == Patient.doctor_id,
        PatientPermission.approved_by_id.in_(approver))
    return query.where(Patient.id.in_(permitted))


def can_patient(patient_id, permission):
    return db.session.scalar(patient_scope(permission).with_only_columns(Patient.id).where(Patient.id == patient_id)) is not None


def accessible_patient(patient_id, permission='operational'):
    patient = db.session.scalar(patient_scope(permission).where(Patient.id == patient_id))
    if not patient:
        abort(404)
    return patient


def appointment_institution(institution_id):
    # SQLite and older local records can omit the redundant appointment scope.
    # The caller still has to check the authoritative patient institution.
    return (Appointment.institution_id == institution_id) | Appointment.institution_id.is_(None)


def audit(action, resource, resource_id):
    db.session.add(AuditEvent(institution_id=g.membership.institution_id,
        actor_id=current_user.id, action=action, resource_type=resource, resource_id=resource_id))


def audit_views(resource, rows):
    """IDs, actor, action and time only. No names, clinical text, request bodies or query strings."""
    for row in rows:
        audit('view_sensitive', resource, row.id)
    db.session.commit()  # audit writes only; never change operational state on GET


def continuity_scope():
    from sqlalchemy import and_, or_
    from models import ContinuityEvent
    def ids(permission):
        return patient_scope(permission).with_only_columns(Patient.id)
    return select(ContinuityEvent).where(
        ContinuityEvent.institution_id == g.membership.institution_id,
        or_(and_(ContinuityEvent.category == 'administrative', ContinuityEvent.patient_id.in_(ids('operational'))),
            and_(ContinuityEvent.category == 'clinical', ContinuityEvent.patient_id.in_(ids('clinical_events'))),
            and_(ContinuityEvent.category == 'patient_reported', ContinuityEvent.patient_id.in_(ids('patient_concerns')))))
