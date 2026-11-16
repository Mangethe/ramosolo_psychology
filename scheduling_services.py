"""Shared, fail-closed availability and versioned operational changes.

Proposals are advisory: no slot hold. All writers serialize on the doctor's user
row, then re-read appointments. UTC storage, Johannesburg policy days.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
import uuid
from flask import abort, g, current_app
from flask_login import current_user
from sqlalchemy import select, func, update
from extensions import db
from models import (User, Membership, Appointment, Patient, AvailabilityPolicy,
    AvailabilitySession, AvailabilityException, PublicHoliday, CalendarBlock,
    AppointmentProposal, CalendarHistory)
from medical_services import utcnow, TZ
from access import audit


def digest(value):
    return sha256(value.encode()).hexdigest()


def lock_doctor(doctor_id, institution_id):
    member = db.session.scalar(select(Membership.id).join(User, User.id==Membership.user_id).where(
        Membership.user_id==doctor_id, Membership.institution_id==institution_id,
        Membership.role=='dr', Membership.enabled.is_(True), User.enabled.is_(True)))
    if not member:
        abort(404)
    db.session.scalar(select(User).where(User.id==doctor_id).with_for_update().execution_options(populate_existing=True))


def local_day(value):
    return value.replace(tzinfo=timezone.utc).astimezone(TZ).date()


def utc_on(day, time):
    return datetime.combine(day,time,TZ).astimezone(timezone.utc).replace(tzinfo=None)


def occupied_until(appointment):
    # Legacy visits without duration metadata reserve the longest supported visit
    # plus break; never guess a short visit and offer a potentially occupied time.
    return (appointment.occupied_until or
        ((appointment.ends_at or appointment.starts_at+timedelta(minutes=240))+timedelta(minutes=10)))


def available_slots(patient, day, care_type='outpatient', visit_kind='followup', exclude=None):
    if care_type not in ('outpatient','inpatient') or visit_kind not in ('followup','first','assessment'):
        raise ValueError('Choose a listed session and visit type.')
    policy=db.session.scalar(select(AvailabilityPolicy).where(
        AvailabilityPolicy.institution_id==patient.institution_id, AvailabilityPolicy.doctor_id==patient.doctor_id,
        AvailabilityPolicy.enabled.is_(True), AvailabilityPolicy.holidays_confirmed.is_(True)))
    if not policy or day<local_day(utcnow()) or day>local_day(utcnow())+timedelta(days=policy.horizon_days):
        return []
    exceptions=list(db.session.scalars(select(AvailabilityException).where(
        AvailabilityException.policy_id==policy.id, AvailabilityException.day==day)))
    holiday=db.session.scalar(select(PublicHoliday.id).where(PublicHoliday.institution_id==patient.institution_id,
        PublicHoliday.day==day))
    closed=bool(holiday or any(e.kind in ('leave','closure') for e in exceptions))
    openings=[e for e in exceptions if e.kind=='opening' and e.care_type==care_type and (not closed or e.override_closure)]
    sessions=[] if closed else list(db.session.scalars(select(AvailabilitySession).where(
        AvailabilitySession.policy_id==policy.id, AvailabilitySession.weekday==day.weekday(),
        AvailabilitySession.care_type==care_type)))
    sessions+=openings
    # Read all occupancy for collision checks, never return identities to callers.
    start=utc_on(day,datetime.min.time()); end=start+timedelta(days=1)
    rows=list(db.session.scalars(select(Appointment).where(
        (Appointment.institution_id==patient.institution_id) | Appointment.patient_id.in_(
            select(Patient.id).where(Patient.institution_id==patient.institution_id)),
        Appointment.status.in_(('scheduled','completed','no_show','held')),
        Appointment.starts_at<end, Appointment.starts_at>=start-timedelta(days=1),
        (Appointment.doctor_id==patient.doctor_id)|(Appointment.patient_id==patient.id),
        Appointment.id != (exclude or -1)).execution_options(populate_existing=True)))
    rows=[a for a in rows if a.status!='held' or a.hold_expires_at is None or a.hold_expires_at>utcnow()]
    # Count all confirmed same-day doctor's visits; changing a booking excludes only itself.
    if sum(a.doctor_id==patient.doctor_id and local_day(a.starts_at)==day for a in rows)>=policy.daily_limit:
        return []
    blocks=list(db.session.scalars(select(CalendarBlock).where(CalendarBlock.institution_id==patient.institution_id,
        CalendarBlock.doctor_id==patient.doctor_id, CalendarBlock.enabled.is_(True),
        CalendarBlock.starts_at<end,CalendarBlock.ends_at>start)))
    result={}
    for session in sessions:
        duration={'followup':session.duration_minutes,'first':session.first_minutes,'assessment':session.assessment_minutes}[visit_kind]
        if not duration or duration<=0 or session.break_minutes is None or session.break_minutes<5:
            continue
        cursor=utc_on(day,session.opens_at); close=utc_on(day,session.closes_at)
        while cursor+timedelta(minutes=duration+session.break_minutes)<=close:
            ends=cursor+timedelta(minutes=duration); occupied=ends+timedelta(minutes=session.break_minutes)
            collision=any(cursor < occupied_until(a) and occupied>a.starts_at for a in rows)
            blocked=any(cursor<b.ends_at and occupied>b.starts_at for b in blocks)
            if cursor>utcnow() and not collision and not blocked:result[cursor]=(ends,occupied)
            cursor=occupied
    return [(start,*result[start]) for start in sorted(result)]


def validate_slot(patient, starts, care_type, visit_kind, exclude=None):
    slot=next((s for s in available_slots(patient,local_day(starts),care_type,visit_kind,exclude) if s[0]==starts),None)
    if slot is None:
        raise ValueError('This time is unavailable or no approved availability policy is configured. Choose another available time.')
    return slot


def history(appointment,action,old=None,new=None,reason='',proposal=None,actor=None):
    db.session.add(CalendarHistory(institution_id=appointment.patient.institution_id,
        appointment_id=appointment.id,proposal_id=proposal.id if proposal else None,
        actor_id=actor if actor else (current_user.id if current_user.is_authenticated else None),
        action=action,original_at=old,new_at=new,reason=reason))


def expire_proposals(appointment):
    for p in db.session.scalars(select(AppointmentProposal).where(AppointmentProposal.appointment_id==appointment.id,
            AppointmentProposal.state=='pending').with_for_update().execution_options(populate_existing=True)):
        if p.expires_at<=utcnow():
            p.state='expired';history(appointment,'proposal_expired',proposal=p)


def refresh_reminders(appointment):
    # Existing dashboard reminders are derived from starts_at, so update immediately.
    # Invalidate durable old-version jobs; never send or fabricate consent here.
    from coordination_services import legacy_table
    outbox=legacy_table('notification_outbox')
    if outbox is not None:
        values={'state':'cancelled'}
        if 'invalidated_at' in outbox.c:values['invalidated_at']=utcnow()
        if 'result_code' in outbox.c:values['result_code']='calendar_changed'
        old_jobs=update(outbox).where(outbox.c.institution_id==appointment.patient.institution_id,
            outbox.c.appointment_id==appointment.id,outbox.c.state.in_(('pending','failed')),
            outbox.c.sent_at.is_(None))
        if appointment.status=='scheduled' and 'appointment_version' in outbox.c:
            old_jobs=old_jobs.where(outbox.c.appointment_version!=appointment.schedule_version)
        db.session.execute(old_jobs.values(**values))
        # Reuse approved reminder policy/leads and explicit in-app consent. External
        # channels remain disabled. Smaller legacy schemas only support invalidation.
        policies=legacy_table('reminder_policies');leads=legacy_table('reminder_leads')
        preferences=legacy_table('communication_preferences')
        from coordination_services import communication_allowed
        if (appointment.status=='scheduled' and policies is not None and leads is not None and preferences is not None
                and 'appointment_version' in outbox.c and appointment.patient.user_id
                and communication_allowed(appointment.patient_id,'reminders','portal',check_window=False)):
            policy=db.session.execute(select(policies).where(policies.c.institution_id==appointment.patient.institution_id,
                policies.c.enabled.is_(True))).mappings().first()
            preference=db.session.execute(select(preferences).where(preferences.c.institution_id==appointment.patient.institution_id,
                preferences.c.patient_id==appointment.patient_id,preferences.c.in_app_enabled.is_(True),
                preferences.c.in_app_consent_at.is_not(None))).mappings().first()
            if policy and preference:
                for minutes in db.session.scalars(select(leads.c.minutes).where(leads.c.policy_id==policy['id'])):
                    due=appointment.starts_at-timedelta(minutes=minutes)
                    if due<utcnow()-timedelta(minutes=policy['catchup_minutes']):continue
                    duplicate=db.session.scalar(select(outbox.c.id).where(outbox.c.appointment_id==appointment.id,
                        outbox.c.appointment_version==appointment.schedule_version,outbox.c.lead_minutes==minutes,
                        outbox.c.channel=='in_app'))
                    if duplicate:continue
                    db.session.execute(outbox.insert().values(public_id=uuid.uuid4().hex,institution_id=appointment.patient.institution_id,
                        appointment_id=appointment.id,appointment_version=appointment.schedule_version,scheduled_start=appointment.starts_at,
                        preference_id=preference['id'],recipient_user_id=appointment.patient.user_id,preference_version=preference['version'],
                        consent_at=preference['in_app_consent_at'],policy_id=policy['id'],policy_version=policy['version'],lead_minutes=minutes,
                        channel='in_app',due_at=due,next_attempt_at=max(due,utcnow()),state='pending',attempt_count=0,
                        max_attempts=policy['max_attempts'],created_at=utcnow()))
    from continuity_services import archive_events
    archive_events(appointment.patient,('missed_appointment','unconfirmed_booking','failed_reminder'),
        'Appointment schedule updated.',appointment.id)


def change(appointment,patient,starts,expected,reason,proposal=None):
    if appointment.status!='scheduled' or appointment.starts_at<=utcnow():abort(403)
    if expected!=appointment.schedule_version:abort(409)
    slot=validate_slot(patient,starts,appointment.care_type or 'outpatient',appointment.visit_kind or 'followup',appointment.id)
    old=appointment.starts_at
    # CAS protects SQLite too; PostgreSQL additionally holds the doctor's row lock.
    result=db.session.execute(update(Appointment).where(Appointment.id==appointment.id,
        Appointment.schedule_version==expected,Appointment.status=='scheduled').values(
        starts_at=slot[0],ends_at=slot[1],occupied_until=slot[2],schedule_version=expected+1))
    if result.rowcount!=1:abort(409)
    db.session.refresh(appointment)
    history(appointment,'proposal_accepted' if proposal else 'staff_confirmed_change',old,starts,reason,proposal)
    for other in db.session.scalars(select(AppointmentProposal).where(
            AppointmentProposal.appointment_id==appointment.id,AppointmentProposal.state=='pending')):
        other.state='accepted' if proposal and other.id==proposal.id else 'superseded'
        other.responded_at=utcnow()
    refresh_reminders(appointment)


def propose(appointment, patient, starts, expected, reason):
    if appointment.status!='scheduled' or appointment.starts_at<=utcnow():abort(403)
    if expected!=appointment.schedule_version:abort(409)
    if not reason or len(reason)>240:abort(400)
    validate_slot(patient,starts,appointment.care_type or 'outpatient',appointment.visit_kind or 'followup',appointment.id)
    expire_proposals(appointment)
    for old in db.session.scalars(select(AppointmentProposal).where(AppointmentProposal.appointment_id==appointment.id,
            AppointmentProposal.state=='pending')):
        old.state='superseded';history(appointment,'proposal_superseded',proposal=old)
    db.session.flush()
    token=secrets.token_urlsafe(32);code=str(secrets.randbelow(1000000)).zfill(6)
    proposal=AppointmentProposal(institution_id=patient.institution_id,appointment_id=appointment.id,
        actor_id=current_user.id,base_version=expected,original_at=appointment.starts_at,proposed_at=starts,
        reason=reason,expires_at=min(utcnow()+timedelta(hours=24),appointment.starts_at,starts),
        token_digest=digest(token),code_digest=digest(code))
    db.session.add(proposal);db.session.flush();history(appointment,'proposal_created',appointment.starts_at,starts,reason,proposal)
    # Sandbox adapter is an in-memory sink only; no SMTP/SMS/network adapter is called.
    from coordination_services import communication_allowed, latest_decision
    if not patient.user_id and communication_allowed(patient.id,'administrative_contact','email'):
        decision=latest_decision(patient.id,'administrative_contact','email')
        proposal.communication_decision_id=decision.id
        sink=current_app.config.get('CALENDAR_SYNTHETIC_DELIVERIES')
        if isinstance(sink,list):sink.append({'proposal_id':proposal.id,'destination':decision.destination,
            'token':token,'code':code,'text':'Please review a proposed appointment time. The original booking remains confirmed.'})
    audit('propose_change','appointment',appointment.id)
    return proposal
