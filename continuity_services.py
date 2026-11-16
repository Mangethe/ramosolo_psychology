"""Supportive workflow only: no diagnoses, scoring, treatment or access mutations."""
from datetime import timedelta
from flask import g
from flask_login import current_user
from sqlalchemy import select
from extensions import db
from access import audit, can_patient, capability
from models import (CarePlan, ContinuityEvent, ContinuityHistory, Membership,
                    CareAssignment, User)
from medical_services import utcnow

KINDS = {
    'missed_appointment': 'administrative', 'unconfirmed_booking': 'administrative',
    'failed_reminder': 'administrative', 'overdue_followup': 'administrative',
    'contact_request': 'patient_reported', 'check_in': 'patient_reported',
    'deterioration': 'clinical', 'lapse': 'clinical', 'relapse': 'clinical',
}
LIVE = ('open', 'acknowledged', 'escalated')


def current_plan(patient):
    return db.session.scalar(select(CarePlan).where(
        CarePlan.institution_id == g.membership.institution_id,
        CarePlan.patient_id == patient.id).order_by(CarePlan.id.desc()).limit(1))


def team(patient):
    """Only enabled, assigned clinical staff can own a follow-up."""
    nurses = select(CareAssignment.nurse_id).where(CareAssignment.patient_id == patient.id)
    return list(db.session.scalars(select(User).join(Membership, Membership.user_id == User.id).where(
        Membership.institution_id == patient.institution_id, Membership.enabled.is_(True),
        User.enabled.is_(True),
        ((Membership.role == 'dr') & (User.id == patient.doctor_id)) |
        ((Membership.role == 'nurse') & User.id.in_(nurses))).order_by(User.name)))


def history(event, action, detail):
    db.session.add(ContinuityHistory(event_id=event.id, actor_id=current_user.id,
                                    action=action, detail=detail))
    audit(action, 'continuity_event', event.id)


def record_event(patient, kind, reason, source_key, appointment=None):
    if not can_patient(patient.id, 'operational'):
        raise ValueError('Patient is outside the current institution or assignment.')
    plan = current_plan(patient)
    if kind not in KINDS or not plan or kind not in plan.rules:
        raise ValueError('No clinician-approved rule for this event. Contact the care team through the usual channel.')
    if plan.owner_id not in [u.id for u in team(patient)]:
        raise ValueError('The responsible care-team member is unavailable. A clinician must update the plan.')
    if KINDS[kind] == 'clinical' and (not capability('clinical_author') or not can_patient(patient.id, 'clinical_events')):
        raise ValueError('Only the assigned clinician can record a clinical event.')
    query = select(ContinuityEvent).where(
        ContinuityEvent.institution_id == patient.institution_id,
        ContinuityEvent.patient_id == patient.id, ContinuityEvent.kind == kind,
        ContinuityEvent.source_key == source_key)
    # Replaying the same resolved administrative source must not reopen an obsolete alert.
    if KINDS[kind] != 'administrative':
        query = query.where(ContinuityEvent.state.in_(LIVE))
    existing = db.session.scalar(query.order_by(ContinuityEvent.id.desc()).limit(1))
    if existing:
        # Preserve additional reports without duplicating the alert or resetting its due time.
        if KINDS[kind] in ('patient_reported', 'clinical'):
            detail = reason
            if KINDS[kind] == 'clinical':
                detail = 'Clinician-approved plan #%s. Definition: %s\n%s' % (plan.id, plan.clinical_definitions, reason)
            history(existing, 'submission' if KINDS[kind] == 'patient_reported' else 'clinical_update', detail)
        return existing
    event = ContinuityEvent(institution_id=patient.institution_id, patient_id=patient.id,
        plan_id=plan.id, author_id=current_user.id, owner_id=plan.owner_id,
        category=KINDS[kind], kind=kind, source_key=source_key,
        appointment_id=appointment.id if appointment else None, reason=reason,
        definition=plan.clinical_definitions if KINDS[kind] == 'clinical' else '',
        due_at=utcnow() + timedelta(minutes=plan.rules[kind]), state='open')
    db.session.add(event)
    db.session.flush()
    history(event, 'created', 'Follow-up opened using clinician-approved plan #%s.' % plan.id)
    return event


def archive_events(patient, kinds, detail, appointment_id=None):
    query = select(ContinuityEvent).where(ContinuityEvent.institution_id == patient.institution_id,
        ContinuityEvent.patient_id == patient.id, ContinuityEvent.kind.in_(kinds),
        ContinuityEvent.state.in_(LIVE))
    if appointment_id is not None:
        query = query.where(ContinuityEvent.appointment_id == appointment_id)
    for event in db.session.scalars(query):
        event.state = 'archived'
        history(event, 'archived', detail)
