from datetime import timedelta, timezone
from zoneinfo import ZoneInfo
from flask import abort, g
from flask_login import current_user
from sqlalchemy import select, or_, MetaData, Table, inspect, update, func
from extensions import db
from access import audit, patient_scope, can_patient, continuity_scope
from medical_services import utcnow
from models import (Patient, Membership, User, CareAssignment, CarePlan, Admission,
    ContinuityEvent, ContinuityNotification, CommunicationDecision, CoordinationPolicy,
    CoordinationHistory, DischargeFollowup, Referral, CareReview, PatientPreference)
from models import CoordinationCoverage

PURPOSES = ('reminders','administrative_contact','referral_sharing','care_plan_sharing')
CHANNELS = ('portal','phone','email','sms')
REFERRAL_TRANSITIONS = {
    'draft': {'sent','cancelled'}, 'sent': {'acknowledged','declined','cancelled'},
    'acknowledged': {'accepted','declined','cancelled'},
    'accepted': {'appointment_arranged','declined','cancelled'},
    'appointment_arranged': {'completed','cancelled'},
    'completed': set(), 'declined': set(), 'cancelled': set(),
}


def record_history(kind, row, action, previous_owner=None, outcome='',previous_cover=None):
    if row.id is None:db.session.flush()
    db.session.add(CoordinationHistory(institution_id=g.membership.institution_id,
        source_type=kind, source_id=row.id, actor_id=current_user.id, action=action,
        previous_owner_id=previous_owner,owner_id=getattr(row,'owner_id',None),outcome_code=outcome,
        previous_cover_id=previous_cover,cover_id=getattr(row,'cover_id',None)))
    audit(action,kind,row.id)


def coverage_query(kind,user_id):
    latest=select(func.max(CoordinationCoverage.id)).where(
        CoordinationCoverage.institution_id==g.membership.institution_id,
        CoordinationCoverage.user_id==user_id,CoordinationCoverage.kind==kind
        ).group_by(CoordinationCoverage.patient_id).correlate(None)
    approvers=select(Membership.user_id).join(User,User.id==Membership.user_id).where(
        Membership.institution_id==g.membership.institution_id,Membership.role=='dr',
        Membership.enabled.is_(True),User.enabled.is_(True))
    return select(CoordinationCoverage.patient_id).join(Patient,Patient.id==CoordinationCoverage.patient_id).where(
        CoordinationCoverage.id.in_(latest),CoordinationCoverage.status=='granted',
        CoordinationCoverage.valid_until>utcnow(),Patient.institution_id==g.membership.institution_id,
        CoordinationCoverage.approved_by_id==Patient.doctor_id,
        CoordinationCoverage.approved_by_id.in_(approvers)).correlate(None)


def coordination_patient_scope(kind=None):
    if g.membership.role!='dr' or kind is None:return patient_scope()
    return select(Patient).where(Patient.institution_id==g.membership.institution_id,
        or_(Patient.doctor_id==current_user.id,Patient.id.in_(coverage_query(kind,current_user.id))))


def coordination_patient(patient_id,kind=None):
    row=db.session.scalar(coordination_patient_scope(kind).where(Patient.id==patient_id))
    if not row:abort(404)
    return row


def lock_patient(patient_id,kind=None):
    row=db.session.scalar(coordination_patient_scope(kind).where(Patient.id==patient_id).with_for_update())
    if not row:abort(404)
    if kind and g.membership.role=='dr' and row.doctor_id!=current_user.id:
        # Recheck delegated authorization after waiting for the patient lock, using a fresh statement.
        if db.session.scalar(coordination_patient_scope(kind).with_only_columns(Patient.id).where(Patient.id==patient_id)) is None:abort(404)
    return row


def staff_team(patient, clinical_only=False,kind=None):
    nurses=select(CareAssignment.nurse_id).where(CareAssignment.patient_id==patient.id)
    covering=[]
    if kind:
        candidates=db.session.scalars(select(Membership.user_id).where(Membership.institution_id==patient.institution_id,
            Membership.role=='dr',Membership.enabled.is_(True)))
        covering=[identity for identity in candidates if db.session.scalar(
            coverage_query(kind,identity).where(CoordinationCoverage.patient_id==patient.id)) is not None]
    allowed=((Membership.role=='dr') & ((Membership.user_id==patient.doctor_id)|Membership.user_id.in_(covering))) | (
        (Membership.role=='nurse') & Membership.user_id.in_(nurses))
    doctor_active=db.session.scalar(select(Membership.id).join(User,User.id==Membership.user_id).where(
        Membership.user_id==patient.doctor_id,Membership.institution_id==patient.institution_id,
        Membership.role=='dr',Membership.enabled.is_(True),User.enabled.is_(True)))
    if not clinical_only and doctor_active:
        allowed=allowed | ((Membership.role=='dr_assist') & (Membership.supervising_doctor_id==patient.doctor_id))
    return list(db.session.execute(select(User.id,User.name,Membership.role).join(Membership, Membership.user_id==User.id).where(
        Membership.institution_id==patient.institution_id,Membership.enabled.is_(True),User.enabled.is_(True),allowed)
        .order_by(User.name)))


def validate_owner(patient, identity, clinical_only=False, doctor_only=False,kind=None):
    if identity is None:return
    team=staff_team(patient,clinical_only,kind)
    if identity not in [u.id for u in team]:abort(400)
    if doctor_only and identity not in [u.id for u in team if u.role=='dr']:abort(400)


def latest_policy(kind):
    return db.session.scalar(select(CoordinationPolicy).where(
        CoordinationPolicy.institution_id==g.membership.institution_id,CoordinationPolicy.kind==kind)
        .order_by(CoordinationPolicy.version.desc()).limit(1))


def latest_decision(patient_id,purpose,channel,scope='practice',*,institution_id=None):
    if institution_id is None:
        institution_id = g.membership.institution_id
    return db.session.scalar(select(CommunicationDecision).where(
        CommunicationDecision.institution_id==institution_id,
        CommunicationDecision.patient_id==patient_id,CommunicationDecision.purpose==purpose,
        CommunicationDecision.channel==channel,CommunicationDecision.scope.in_((scope,'*')))
        .order_by(CommunicationDecision.id.desc()).limit(1))


def communication_allowed(patient_id,purpose,channel,scope='practice',check_window=True):
    decision=latest_decision(patient_id,purpose,channel,scope)
    if decision is None and purpose=='reminders' and channel=='portal' and scope=='practice':
        # Preserve an existing explicit in-app reminder opt-in, never infer one from a booking.
        preferences=legacy_table('communication_preferences')
        if preferences is not None:
            return db.session.scalar(select(preferences.c.id).join(Patient,Patient.id==preferences.c.patient_id).join(
                User,User.id==Patient.user_id).join(Membership,Membership.user_id==User.id).where(preferences.c.institution_id==g.membership.institution_id,
                preferences.c.patient_id==patient_id,Patient.institution_id==g.membership.institution_id,
                Membership.institution_id==g.membership.institution_id,Membership.role=='patient',Membership.enabled.is_(True),
                User.enabled.is_(True),preferences.c.in_app_enabled.is_(True),preferences.c.in_app_consent_at.is_not(None)).limit(1)) is not None
    return verified_communication_allowed(decision, check_window=check_window)


def verified_communication_allowed(decision, *, check_window=True):
    if not decision or decision.status!='granted' or not decision.destination or not decision.verified_at:
        return False
    if check_window and decision.contact_start and decision.contact_end:
        local=utcnow().replace(tzinfo=timezone.utc).astimezone(ZoneInfo(decision.timezone)).time()
        start,end=decision.contact_start,decision.contact_end
        in_window=start<=local<=end if start<=end else local>=start or local<=end
        if not in_window:return False
    return True


def legacy_table(name):
    # Reflect existing infrastructure only; never create or replace its schema/model.
    connection=db.session.connection()
    if not inspect(connection).has_table(name):return None
    return Table(name,MetaData(),autoload_with=connection)


def suppress_unsent(patient,purpose,channel,scope='*',reason='consent_withdrawn'):
    event_ids=select(ContinuityEvent.id).where(ContinuityEvent.institution_id==patient.institution_id,
        ContinuityEvent.patient_id==patient.id)
    query=select(ContinuityNotification).where(ContinuityNotification.event_id.in_(event_ids),
        ContinuityNotification.purpose==purpose,ContinuityNotification.channel==channel,
        ContinuityNotification.state=='queued')
    if scope!='*':query=query.where(ContinuityNotification.scope==scope)
    for notice in db.session.scalars(query):
        notice.state='suppressed';notice.result_code=reason
        audit('suppress_optional_notice','continuity_notification',notice.id)
    # The verified current outbox is in-app reminders only. Do not repurpose it for referrals.
    if purpose=='reminders' and channel=='portal' and scope in ('practice','*'):
        outbox=legacy_table('notification_outbox')
        preferences=legacy_table('communication_preferences')
        if preferences is not None:
            db.session.execute(update(preferences).where(preferences.c.institution_id==patient.institution_id,
                preferences.c.patient_id==patient.id,preferences.c.in_app_enabled.is_(True)).values(in_app_enabled=False,
                    version=preferences.c.version+1,changed_by=current_user.id,changed_at=utcnow()))
        if outbox is not None:
            from models import Appointment
            appts=select(Appointment.id).where(Appointment.patient_id==patient.id)
            ids=list(db.session.scalars(select(outbox.c.id).where(
                outbox.c.institution_id==patient.institution_id,outbox.c.appointment_id.in_(appts),
                outbox.c.state.in_(('pending','failed')),outbox.c.sent_at.is_(None)).with_for_update()))
            if ids:
                db.session.execute(update(outbox).where(outbox.c.id.in_(ids),
                    outbox.c.institution_id==patient.institution_id).values(state='cancelled',
                        invalidated_at=utcnow(),result_code='coordination_'+reason))
                for identity in ids:audit('suppress_optional_notice','notification_outbox',identity)


def recheck_queued(patient):
    event_ids=select(ContinuityEvent.id).where(ContinuityEvent.institution_id==patient.institution_id,
        ContinuityEvent.patient_id==patient.id)
    for notice in db.session.scalars(select(ContinuityNotification).where(
            ContinuityNotification.event_id.in_(event_ids),ContinuityNotification.state=='queued')):
        if not communication_allowed(patient.id,notice.purpose,notice.channel,notice.scope,False):
            notice.state='suppressed';notice.result_code='consent_or_destination_changed'
            audit('suppress_optional_notice','continuity_notification',notice.id)
    decision=latest_decision(patient.id,'reminders','portal')
    if decision is not None:
        if not communication_allowed(patient.id,'reminders','portal',check_window=False):
            suppress_unsent(patient,'reminders','portal',reason='consent_or_destination_changed')
        return
    outbox=legacy_table('notification_outbox');preferences=legacy_table('communication_preferences')
    if outbox is None:return
    from models import Appointment
    selected=[outbox.c.id,outbox.c.appointment_id]
    if 'preference_id' in outbox.c:selected.append(outbox.c.preference_id)
    jobs=db.session.execute(select(*selected).where(outbox.c.institution_id==patient.institution_id,
        outbox.c.appointment_id.in_(select(Appointment.id).where(Appointment.patient_id==patient.id)),
        outbox.c.state.in_(('pending','failed')),outbox.c.sent_at.is_(None)).with_for_update()).mappings()
    for job in jobs:
        valid=False
        if preferences is not None and 'preference_id' in job:
            base=select(preferences.c.id).where(preferences.c.id==job['preference_id'],
                preferences.c.institution_id==patient.institution_id,preferences.c.in_app_enabled.is_(True),
                preferences.c.in_app_consent_at.is_not(None))
            registered=base.where(preferences.c.patient_id==patient.id)
            valid=db.session.scalar(registered) is not None and communication_allowed(patient.id,'reminders','portal')
            # Keep a verified guest booking opt-in bound to its original booking, never promote it to patient consent.
            if not valid and all(c in preferences.c for c in ('guest_verified_digest','booking_request_id')):
                appointments=legacy_table('appointments')
                if 'booking_request_id' in appointments.c:
                    booking=db.session.scalar(select(appointments.c.booking_request_id).where(
                        appointments.c.id==job['appointment_id'],appointments.c.patient_id==patient.id))
                    if booking is not None:
                        valid=db.session.scalar(base.where(preferences.c.booking_request_id==booking,
                            preferences.c.guest_verified_digest.is_not(None),func.length(preferences.c.guest_verified_digest)>0)) is not None
        elif 'preference_id' not in job:
            valid=communication_allowed(patient.id,'reminders','portal',check_window=False)
        if not valid:
            db.session.execute(update(outbox).where(outbox.c.id==job['id'],outbox.c.institution_id==patient.institution_id,
                outbox.c.state.in_(('pending','failed')),outbox.c.sent_at.is_(None)).values(
                    state='cancelled',invalidated_at=utcnow(),result_code='coordination_legacy_consent_unverified'))
            audit('suppress_optional_notice','notification_outbox',job['id'])


def ensure_discharge(admission,patient):
    row=db.session.scalar(select(DischargeFollowup).where(
        DischargeFollowup.admission_id==admission.id,DischargeFollowup.institution_id==patient.institution_id))
    if not row:
        row=DischargeFollowup(institution_id=patient.institution_id,patient_id=patient.id,
            admission_id=admission.id)
        db.session.add(row);db.session.flush();record_history('discharge_followup',row,'followup_required')
    return row


def ensure_review(plan):
    row=db.session.scalar(select(CareReview).where(CareReview.plan_id==plan.id,
        CareReview.institution_id==plan.institution_id,CareReview.status=='pending'))
    if not row:
        sequence=(db.session.scalar(select(func.max(CareReview.sequence)).where(CareReview.plan_id==plan.id)) or 0)+1
        row=CareReview(institution_id=plan.institution_id,patient_id=plan.patient_id,plan_id=plan.id,
            sequence=sequence,owner_id=plan.author_id,due_at=plan.review_at)
        policy=latest_policy('review')
        row.policy_id=policy.id if policy else None
        db.session.add(row);db.session.flush();record_history('care_review',row,'review_scheduled')
    return row


def source_scope(model):
    kind={DischargeFollowup:'discharge',Referral:'referral',CareReview:'review'}.get(model)
    query=select(model).where(model.institution_id==g.membership.institution_id,
        model.patient_id.in_(coordination_patient_scope(kind).with_only_columns(Patient.id)))
    if g.membership.role=='nurse':
        query=query.where(or_(model.owner_id==current_user.id,model.cover_id==current_user.id))
    return query


def source_row(model,identity,lock=False):
    query=source_scope(model).where(model.id==identity)
    if lock:query=query.with_for_update().execution_options(populate_existing=True)
    row=db.session.scalar(query)
    if not row:abort(404)
    return row


def touch(row,version):
    if version!=row.version:abort(409)
    row.version+=1;row.updated_at=utcnow()


def action_items():
    """One projection across source records; no writes on GET and no duplicate tasks."""
    role=g.membership.role;now=utcnow();items=[]
    eligible=set(db.session.scalars(patient_scope().with_only_columns(Patient.id)))
    if role=='dr':
        for kind in ('discharge','referral','review'):
            eligible.update(db.session.scalars(coordination_patient_scope(kind).with_only_columns(Patient.id)))
    patient_rows=list(db.session.scalars(select(Patient).where(Patient.institution_id==g.membership.institution_id,
        Patient.id.in_(eligible))))
    patients={p.id:p for p in patient_rows};ids=list(patients)
    names=select(User.id,User.name).join(Membership,Membership.user_id==User.id).where(
        Membership.institution_id==g.membership.institution_id,Membership.enabled.is_(True),
        Membership.role.in_(('dr','nurse','dr_assist','admin')),User.enabled.is_(True))
    if role=='patient':
        related={user.id for patient in patient_rows for kind in ('discharge','referral','review')
            for user in staff_team(patient,kind=kind)}
        names=names.where(User.id.in_(related))
    users={u.id:u.name for u in db.session.execute(names)}
    policies={k:latest_policy(k) for k in ('discharge','review')}
    def add(kind,source,row,patient_id,title,url,status,owner=None,due=None,last=None,escalated=False,
            unavailable=False,missing=False):
        valid_owners={u.id for u in staff_team(patients[patient_id],kind in ('discharge','review'),kind)} if kind in ('discharge','review','referral') else set(users)
        unavailable=unavailable or (owner is not None and owner not in valid_owners)
        attention='Completed' if status in ('completed','closed','cancelled','declined','archived','superseded','resolved','obsolete') else (
            'Owner unavailable' if unavailable or (owner is not None and owner not in users) else
            'Unassigned' if owner is None else 'Missing due date' if due is None else
            'Overdue' if due<now else 'Due soon' if policies.get(kind) and due<=now+timedelta(days=policies[kind].due_soon_days) else 'Pending')
        if missing and attention=='Pending':attention='Planning incomplete'
        reasons=[]
        if attention=='Completed':reasons=['Completed']
        else:
            if owner is None:reasons.append('Unassigned')
            if due is None:reasons.append('Missing due date')
            if unavailable or (owner is not None and owner not in users):reasons.append('Owner unavailable')
            if due and due<now:reasons.append('Overdue')
            elif due and policies.get(kind) and due<=now+timedelta(days=policies[kind].due_soon_days):reasons.append('Due soon')
            if missing:reasons.append('Planning incomplete')
            if escalated:reasons.append('Escalated')
            if not reasons:reasons=['Pending']
        items.append(dict(key=f'{source}:{row}',type=kind,source=source,source_id=row,
            patient_id=patient_id,patient=patients[patient_id].name,action=title,url=url,status=status,
            owner_id=owner,owner=users.get(owner,'Unavailable' if owner else 'Unassigned'),due_at=due,
            attention=' · '.join(reasons),reasons=reasons,last_activity=last,escalated=escalated))
    from flask import url_for
    from models import Appointment
    discharges=list(db.session.scalars(select(DischargeFollowup).where(
        DischargeFollowup.institution_id==g.membership.institution_id,
        DischargeFollowup.patient_id.in_(coordination_patient_scope('discharge').with_only_columns(Patient.id)))))
    by_admission={r.admission_id:r for r in discharges}
    if role!='dr_assist':
        for admission in db.session.scalars(select(Admission).where(Admission.patient_id.in_(
                coordination_patient_scope('discharge').with_only_columns(Patient.id)))):
            if role=='dr' and db.session.scalar(coordination_patient_scope('discharge').with_only_columns(Patient.id).where(Patient.id==admission.patient_id)) is None:continue
            row=by_admission.get(admission.id)
            if role=='patient':
                if not row or not row.patient_visible:continue
            if role=='nurse' and (not row or current_user.id not in (row.owner_id,row.cover_id)):continue
            if not row and not admission.discharged_at:continue
            add('discharge','admission',admission.id,admission.patient_id,
                row.agreed_action if role=='patient' else 'Complete discharge follow-up' if row and row.planning_complete else 'Assign discharge follow-up owner and deadline',
                url_for('med.discharge_followup',admission_id=admission.id) if role!='patient' else url_for('med.my_agreed_actions'),
                row.status if row else 'open',row.owner_id if row else None,row.due_at if row else None,
                row.updated_at if row else admission.discharged_at,row.escalated if row else False,
                row.owner_unavailable if row else False,not row or not row.planning_complete)
    for row in db.session.scalars(select(Referral).where(Referral.institution_id==g.membership.institution_id,
            Referral.patient_id.in_(coordination_patient_scope('referral').with_only_columns(Patient.id)))):
        if role=='dr' and db.session.scalar(coordination_patient_scope('referral').with_only_columns(Patient.id).where(Patient.id==row.patient_id)) is None:continue
        if role=='patient' and not row.patient_visible:continue
        if role=='nurse' and current_user.id not in (row.owner_id,row.cover_id):continue
        add('referral','referral',row.id,row.patient_id,row.requested_action if role=='patient' else 'Review referral status and next action',
            url_for('med.referral_detail',referral_id=row.id) if role!='patient' else url_for('med.my_agreed_actions'),
            row.status,row.owner_id,row.due_at,row.updated_at,row.escalated,row.owner_unavailable)
        if row.appointment_id and row.status=='appointment_arranged':
            appointment=db.session.scalar(select(Appointment).where(Appointment.id==row.appointment_id,
                Appointment.patient_id==row.patient_id))
            if appointment and appointment.status=='cancelled':
                items[-1]['reasons'].append('Appointment cancelled')
                items[-1]['attention']+=' · Appointment cancelled'
    latest={}
    for plan in db.session.execute(select(CarePlan.id,CarePlan.patient_id,CarePlan.author_id,
            CarePlan.review_at,CarePlan.created_at,CarePlan.patient_visible).where(CarePlan.institution_id==g.membership.institution_id,
            CarePlan.patient_id.in_(coordination_patient_scope('review').with_only_columns(Patient.id))).order_by(CarePlan.id)):
        latest[plan.patient_id]=plan
    for patient_id,plan in latest.items():
        if role=='dr_assist':continue
        if role=='patient' and not (plan.patient_visible and communication_allowed(patient_id,'care_plan_sharing','portal',check_window=False)):continue
        rows=list(db.session.scalars(select(CareReview).where(CareReview.plan_id==plan.id,
            CareReview.institution_id==g.membership.institution_id).order_by(CareReview.sequence)))
        if not rows:rows=[None]
        for row in rows:
            if role=='nurse' and (not row or current_user.id not in (row.owner_id,row.cover_id) or not can_patient(patient_id,'care_plan')):continue
            patient_due=None
            if role=='patient':
                completed=next((r for r in reversed(rows) if r and r.status=='completed'),None)
                patient_due=completed.next_review_at if completed else plan.review_at
            add('review','review',row.id if row else 'plan-'+str(plan.id),patient_id,'Review agreed care plan',
                url_for('med.review_plan',plan_id=plan.id) if role!='patient' else url_for('med.my_care_plan'),
                row.status if row else 'pending',row.owner_id if row else plan.author_id,
                patient_due if role=='patient' else row.due_at if row else plan.review_at,row.updated_at if row else plan.created_at,
                row.escalated if row else False,row.owner_unavailable if row else False)
    # Plan review dates already have one source above; suppress duplicate overdue-review alerts.
    if role!='patient':
        for row in db.session.scalars(continuity_scope().where(ContinuityEvent.kind!='overdue_followup')):
            if role=='nurse' and row.owner_id!=current_user.id:continue
            add('continuity','continuity',row.id,row.patient_id,'Review '+row.kind.replace('_',' '),
                url_for('med.continuity_detail',event_id=row.id),row.state,row.owner_id,row.due_at,
                row.created_at,row.state=='escalated')
        legacy=legacy_table('attendance_followups')
        if legacy is not None:
            columns=[legacy.c.id,legacy.c.appointment_id,legacy.c.rule,legacy.c.state,legacy.c.checked_at,Appointment.patient_id]
            for field in ('owner_id','cover_id','due_at','escalated'):
                if field in legacy.c:columns.append(legacy.c[field])
            rows=db.session.execute(select(*columns).join(Appointment,Appointment.id==legacy.c.appointment_id).where(
                legacy.c.institution_id==g.membership.institution_id,Appointment.patient_id.in_(ids))).mappings()
            rules={'confirmation_due':'unconfirmed_booking','delivery_failed':'failed_reminder','attendance_history':'missed_appointment'}
            for row in rows:
                if role=='nurse' and current_user.id not in (row.get('owner_id'),row.get('cover_id')):continue
                # Prefer the existing scheduling follow-up where both implementations describe the same source.
                matching=[e.id for e in db.session.scalars(continuity_scope().where(
                    ContinuityEvent.appointment_id==row['appointment_id'],ContinuityEvent.kind==rules.get(row['rule'],'none')))]
                if row['state'] in ('open','acknowledged'):
                    items[:]=[item for item in items if not (item['source']=='continuity' and item['source_id'] in matching)]
                add('continuity','attendance',row['id'],row['patient_id'],'Review scheduling follow-up',
                    url_for('med.legacy_followup',followup_id=row['id']),row['state'],row.get('owner_id'),
                    row.get('due_at'),row['checked_at'],row.get('escalated',False))
    return items
