"""Purpose-scoped appointment messages in the transactional email outbox."""
from datetime import timedelta, timezone

from flask import current_app
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from coordination_services import latest_decision, verified_communication_allowed
from extensions import db
from mail_delivery import address
from medical_services import TZ, utcnow
from models import (AccountVerification, Appointment, AppointmentEmail, Institution, Membership,
                    Patient, PatientPreference, SecurityEmail, User)
from portal_sessions import clock

SUBJECTS = {
    'appt_confirmed': ('Appointment confirmed', 'An appointment has been confirmed.'),
    'appt_rescheduled': ('Appointment rescheduled', 'The time of a confirmed appointment has changed.'),
    'appt_cancelled': ('Appointment cancelled', 'A scheduled appointment has been cancelled.'),
    'appt_reminder': ('Appointment reminder', 'You have an upcoming confirmed appointment.'),
}


def current_recipient(patient, kind, *, check_window=False):
    purpose = 'reminders' if kind == 'appt_reminder' else 'administrative_contact'
    preference = db.session.scalar(select(PatientPreference).where(PatientPreference.patient_id == patient.id))
    if preference and (not preference.communication_consent or 'email' not in preference.channels):
        return None
    decision = latest_decision(patient.id, purpose, 'email', institution_id=patient.institution_id)
    if not verified_communication_allowed(decision, check_window=check_window):
        return None
    try:
        destination = address(decision.destination).addr_spec
    except ValueError:
        return None
    if patient.email and patient.email.lower() != destination.lower():
        return None
    if patient.user_id:
        user = db.session.get(User, patient.user_id)
        verified = db.session.get(AccountVerification, patient.user_id)
        membership = db.session.scalar(select(Membership.id).where(Membership.user_id == patient.user_id,
            Membership.institution_id == patient.institution_id, Membership.role == 'patient',
            Membership.enabled.is_(True)))
        if (not membership or not user or not user.enabled or not verified or verified.verified_at is None or
                verified.verified_email != user.email or user.email.lower() != destination.lower()):
            return None
    return decision, destination


def queue(appointment, kind):
    if not current_app.config['APPOINTMENT_EMAIL_ENABLED']:
        return
    patient = appointment.patient
    if not patient or appointment.institution_id not in (None, patient.institution_id):
        return
    db.session.execute(update(SecurityEmail).where(SecurityEmail.state == 'pending',
        SecurityEmail.dedupe_key.in_(select(AppointmentEmail.dedupe_key).where(
            AppointmentEmail.institution_id == patient.institution_id,
            AppointmentEmail.appointment_id == appointment.id,
            AppointmentEmail.schedule_version != appointment.schedule_version))).values(state='cancelled'))
    if kind is None:
        return
    expected = 'cancelled' if kind == 'appt_cancelled' else 'scheduled'
    if appointment.status != expected:
        return
    queue_one(appointment, patient, kind)
    minutes = current_app.config['APPOINTMENT_EMAIL_REMINDER_MINUTES']
    if expected == 'scheduled' and 1 <= minutes <= 10080:
        queue_one(appointment, patient, 'appt_reminder', minutes)


def queue_one(appointment, patient, kind, lead=None):
    chosen = current_recipient(patient, kind)
    if not chosen:
        return
    decision, recipient = chosen
    now = clock()
    due = now
    if lead is not None:
        due_at = appointment.starts_at - timedelta(minutes=lead)
        if due_at <= utcnow():
            return
        due = int(due_at.replace(tzinfo=timezone.utc).timestamp())
    key = f'{kind}:{patient.institution_id}:{appointment.id}:{appointment.schedule_version}'
    insert = postgres_insert if db.session.get_bind().dialect.name == 'postgresql' else sqlite_insert
    inserted = db.session.execute(insert(SecurityEmail).values(dedupe_key=key, kind=kind,
        user_id=patient.user_id, recipient=recipient, created_at=now, next_attempt_at=due,
        state='pending', attempts=0).on_conflict_do_nothing(index_elements=[SecurityEmail.dedupe_key])).rowcount
    if inserted:
        db.session.add(AppointmentEmail(dedupe_key=key, institution_id=patient.institution_id,
            appointment_id=appointment.id, patient_id=patient.id, schedule_version=appointment.schedule_version,
            scheduled_start=appointment.starts_at, decision_id=decision.id, lead_minutes=lead))


def render(job, origin):
    if not current_app.config['APPOINTMENT_EMAIL_ENABLED']:
        return None
    context = db.session.get(AppointmentEmail, job.dedupe_key)
    if context is None:
        return None
    expected = 'cancelled' if job.kind == 'appt_cancelled' else 'scheduled'
    row = db.session.scalar(select(Appointment).where(Appointment.id == context.appointment_id,
        Appointment.patient_id == context.patient_id, Appointment.status == expected,
        (Appointment.institution_id == context.institution_id) | Appointment.institution_id.is_(None),
        Appointment.schedule_version == context.schedule_version, Appointment.starts_at == context.scheduled_start
    ).with_for_update())
    patient = db.session.scalar(select(Patient).join(Institution).where(Patient.id == context.patient_id,
        Patient.institution_id == context.institution_id, Institution.kind == 'medical').with_for_update(of=Patient))
    if not row or not patient or patient.user_id != job.user_id:
        return None
    if job.kind == 'appt_reminder' and context.lead_minutes != current_app.config['APPOINTMENT_EMAIL_REMINDER_MINUTES']:
        return None
    if expected == 'scheduled' and row.starts_at <= utcnow():
        return None
    chosen = current_recipient(patient, job.kind, check_window=True)
    if not chosen or chosen[0].id != context.decision_id or chosen[1] != job.recipient:
        return None
    subject, body = SUBJECTS[job.kind]
    details = latest_decision(patient.id, chosen[0].purpose, 'email', 'appointment_details',
                              institution_id=patient.institution_id)
    if verified_communication_allowed(details) and details.scope == 'appointment_details' and details.destination == job.recipient:
        start = row.starts_at.replace(tzinfo=timezone.utc).astimezone(TZ)
        body += f' Scheduled time {start:%Y-%m-%d %H:%M %Z}.'
    return subject, f'{body}\n\nFor the latest information, visit {origin}/auth/login or contact the practice.'
