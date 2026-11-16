from flask import abort, flash, g, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from extensions import db
from access import (accessible_patient, audit, audit_views, can_patient, continuity_scope,
                    patient_scope, require_roles, require_capability)
from models import (Appointment, CarePlan, ContinuityEvent, ContinuityNotification, Patient, PatientPreference, User)
from medical_services import parse_local, utcnow
from continuity_services import (KINDS, LIVE, archive_events,
                                 current_plan, history, record_event, team)
from . import bp

STAFF = ('dr', 'nurse', 'admin', 'dr_assist')


def text_field(name, limit=4000):
    value = request.form.get(name, '').strip()
    if not value or len(value) > limit:
        abort(400)
    return value


def event_scope():
    return continuity_scope()


@bp.get('/med/continuity')
@require_roles(*STAFF)
def continuity_queue():
    archived = request.args.get('history') == '1'
    query = event_scope().where(ContinuityEvent.state.in_(('closed', 'archived') if archived else LIVE))
    events = list(db.session.scalars(query.order_by(ContinuityEvent.due_at, ContinuityEvent.id)))
    audit_views('continuity_event', events)
    patients = list(db.session.scalars(patient_scope().order_by(Patient.name)))
    return render_template('medical/continuity_queue.html', events=events, patients=patients,
                           archived=archived, now=utcnow(), kinds=KINDS)


@bp.get('/med/patients/<int:patient_id>/care-plan')
@require_capability('clinical_read')
def care_plan(patient_id):
    patient = accessible_patient(patient_id, 'care_plan')
    show_clinical_rules = can_patient(patient.id, 'clinical_events')
    fields = ['id','author_id','owner_id','goals','warning_signs','channels','communication_consent',
        'planned_appointments','review_at','response_steps','urgent_help','monitoring_hours',
        'agreed_at','created_at','patient_visible']
    if show_clinical_rules:
        fields += ['clinical_definitions', 'rules']
    versions = [dict(row) for row in db.session.execute(select(*(getattr(CarePlan, f) for f in fields),
        User.name.label('owner_name')).join(User, User.id == CarePlan.owner_id).where(CarePlan.patient_id == patient.id,
        CarePlan.institution_id == g.membership.institution_id).order_by(CarePlan.id.desc())).mappings()]
    from coordination_services import source_scope
    from models import CareReview
    for version in versions:
        version['review_link']=g.membership.role in ('dr','admin') or db.session.scalar(
            source_scope(CareReview).with_only_columns(CareReview.id).where(CareReview.plan_id==version['id'],
                CareReview.status=='pending').limit(1)) is not None
    for version in versions:
        audit('view_sensitive', 'care_plan', version['id'])
    db.session.commit()
    return render_template('medical/care_plan.html', patient=patient, versions=versions,
                           team=team(patient), kinds=KINDS,
                           show_clinical_rules=show_clinical_rules)


@bp.post('/med/patients/<int:patient_id>/care-plan')
@require_capability('clinical_author')
def save_care_plan(patient_id):
    patient = accessible_patient(patient_id)
    owner_id = request.form.get('owner_id', type=int)
    if owner_id not in [u.id for u in team(patient)]:
        abort(400)
    if request.form.get('patient_agreed') != 'on' or request.form.get('practice_approved') != 'on':
        abort(400)
    try:
        review_at = parse_local(request.form.get('review_at', ''))
        if review_at <= utcnow():
            raise ValueError()
        rules = {}
        for kind in KINDS:
            value = request.form.get('rule_' + kind, '').strip()
            if value:
                minutes = int(value)
                if not 1 <= minutes <= 525600:
                    raise ValueError()
                rules[kind] = minutes
    except (ValueError, TypeError, OverflowError):
        abort(400)
    channels = request.form.getlist('channels')
    if not channels or any(c not in ('phone', 'email', 'sms', 'portal') for c in channels):
        abort(400)
    consent = request.form.get('communication_consent')
    if consent not in ('yes', 'no'):
        abort(400)
    plan = CarePlan(institution_id=patient.institution_id, patient_id=patient.id,
        author_id=current_user.id, owner_id=owner_id, goals=text_field('goals'),
        warning_signs=text_field('warning_signs'), channels=channels,
        communication_consent=consent == 'yes', planned_appointments=text_field('planned_appointments'),
        review_at=review_at, response_steps=text_field('response_steps'), urgent_help=text_field('urgent_help'),
        monitoring_hours=text_field('monitoring_hours', 500), rules=rules,
        clinical_definitions=text_field('clinical_definitions'), agreed_at=utcnow(),
        patient_visible=request.form.get('share_with_patient') == 'on')
    # Serialize plan changes with event creation on PostgreSQL.
    db.session.execute(select(Patient.id).where(Patient.id == patient.id,
        Patient.institution_id == patient.institution_id).with_for_update())
    db.session.add(plan)
    db.session.flush()
    from coordination_services import ensure_review, record_history
    from models import CareReview
    for prior in db.session.scalars(select(CareReview).where(CareReview.patient_id==patient.id,
            CareReview.institution_id==patient.institution_id,CareReview.status=='pending',CareReview.plan_id!=plan.id)):
        prior.status='superseded';prior.updated_at=utcnow();prior.version+=1
        record_history('care_review',prior,'superseded_by_plan_version')
    ensure_review(plan)
    archive_events(patient, ('overdue_followup',), 'Review superseded by a newly agreed care plan.')
    audit('approve_care_plan', 'care_plan', plan.id)
    db.session.commit()
    flash('Agreed care plan saved as a new clinician-approved version.', 'success')
    return redirect(url_for('med.care_plan', patient_id=patient.id))


@bp.post('/med/continuity/events')
@require_roles(*STAFF)
def create_continuity_event():
    patient = accessible_patient(request.form.get('patient_id', type=int))
    kind = request.form.get('kind')
    if kind not in KINDS or KINDS[kind] == 'patient_reported':
        abort(400)
    if KINDS[kind] == 'clinical' and g.membership.role != 'dr':
        abort(403)
    reason = text_field('reason')
    db.session.execute(select(Patient.id).where(Patient.id == patient.id,
        Patient.institution_id == patient.institution_id).with_for_update())
    appointment = None
    if kind in ('missed_appointment', 'unconfirmed_booking', 'failed_reminder'):
        appointment = db.session.scalar(select(Appointment).where(
            Appointment.id == request.form.get('appointment_id', type=int),
            Appointment.patient_id == patient.id))
        if not appointment:
            abort(400)
        if kind == 'missed_appointment' and (appointment.status != 'no_show' or appointment.starts_at > utcnow()):
            abort(400)
        if kind in ('unconfirmed_booking', 'failed_reminder') and appointment.status != 'scheduled':
            abort(400)
        source = 'appointment:%s' % appointment.id
    elif kind == 'overdue_followup':
        plan = current_plan(patient)
        if not plan or plan.review_at > utcnow():
            abort(400)
        source = 'review:%s' % plan.id
    else:
        source = 'clinical:active'
        if request.form.get('definition_confirmed') != 'on':
            abort(400)
    try:
        record_event(patient, kind, reason, source, appointment)
        db.session.commit()
        flash('Follow-up recorded. Existing active alerts are deduplicated.', 'success')
    except ValueError as error:
        db.session.rollback()
        flash(str(error), 'error')
    except IntegrityError:
        db.session.rollback()
        flash('A matching follow-up was recorded concurrently. Refresh the queue.', 'error')
    return redirect(url_for('med.continuity_queue'))


@bp.get('/med/continuity/<int:event_id>')
@require_roles(*STAFF)
def continuity_detail(event_id):
    event = db.session.scalar(event_scope().where(ContinuityEvent.id == event_id))
    if not event:
        abort(404)
    audit_views('continuity_event', [event])
    notices = list(db.session.scalars(select(ContinuityNotification).where(
        ContinuityNotification.event_id == event.id)))
    return render_template('medical/continuity_detail.html', event=event,
                           team=team(event.patient), notices=notices, live=event.state in LIVE,
                           can_read_plan=can_patient(event.patient_id, 'care_plan'),
                           can_update=(event.category == 'administrative' and g.membership.role in ('admin','dr_assist'))
                           or g.membership.role == 'dr' or (g.membership.role == 'nurse' and event.owner_id == current_user.id))


@bp.post('/med/continuity/<int:event_id>')
@require_roles(*STAFF)
def update_continuity_event(event_id):
    meta=db.session.execute(event_scope().with_only_columns(ContinuityEvent.patient_id).where(ContinuityEvent.id==event_id)).first()
    if not meta:abort(404)
    from coordination_services import lock_patient, communication_allowed, latest_decision
    lock_patient(meta.patient_id)
    event = db.session.scalar(event_scope().where(ContinuityEvent.id == event_id).with_for_update().execution_options(populate_existing=True))
    if not event:
        abort(404)
    if event.category != 'administrative' and g.membership.role == 'admin':
        abort(403)  # an explicit read grant never confers clinical authorship or task authority
    if g.membership.role == 'nurse' and event.owner_id != current_user.id:
        abort(403)
    if event.state not in LIVE:
        abort(400)
    action = request.form.get('action')
    if g.membership.role == 'nurse' and action not in (
            'acknowledge','contact_attempt','outcome','escalate','close','sandbox_notification'):
        abort(403)
    detail = text_field('detail')
    if action == 'acknowledge':
        if event.state != 'open':
            abort(400)
        event.state = 'acknowledged'
    elif action in ('contact_attempt', 'outcome'):
        pass
    elif action in ('assign', 'escalate'):
        owner_id = request.form.get('owner_id', type=int)
        if g.membership.role == 'nurse' and owner_id != event.patient.doctor_id:
            abort(403)
        if owner_id not in [u.id for u in team(event.patient)]:
            abort(400)
        detail = 'Owner #%s → #%s. %s' % (event.owner_id, owner_id, detail)
        event.owner_id = owner_id
        if action == 'escalate':
            event.state = 'escalated'
    elif action == 'close':
        event.state = 'closed'
    elif action == 'archive':
        event.state = 'archived'
    elif action == 'sandbox_notification':
        plan = current_plan(event.patient)
        channel = request.form.get('channel')
        if not communication_allowed(event.patient_id,'administrative_contact',channel):abort(400)
        decision=latest_decision(event.patient_id,'administrative_contact',channel)
        if (not plan or not plan.communication_consent or channel not in plan.channels
                or channel not in ('email', 'sms', 'phone', 'portal')):
            abort(400)
        preference = db.session.scalar(select(PatientPreference).where(PatientPreference.patient_id == event.patient_id))
        if preference and (not preference.communication_consent or channel not in preference.channels):
            abort(400)
        if not db.session.scalar(select(ContinuityNotification.id).where(
                ContinuityNotification.event_id == event.id, ContinuityNotification.channel == channel)):
            db.session.add(ContinuityNotification(event_id=event.id, channel=channel,
                body='Please contact the practice through your agreed contact channel.', mode='sandbox',
                purpose='administrative_contact',decision_id=decision.id))
        # Never copy free-text clinical content into notifications or preview history.
        detail = 'Sandbox preview only; no message sent. Channel: ' + channel
    else:
        abort(400)
    history(event, action, detail)
    db.session.commit()
    return redirect(url_for('med.continuity_detail', event_id=event.id))


@bp.get('/med/check-in')
@require_roles('patient')
def check_in():
    patients = list(db.session.scalars(patient_scope()))
    instructions = []
    for patient in patients:
        row = db.session.execute(select(CarePlan.id, CarePlan.monitoring_hours, CarePlan.urgent_help,
            CarePlan.rules['check_in'].as_integer().label('check_in'),
            CarePlan.rules['contact_request'].as_integer().label('contact_request')).where(
                CarePlan.patient_id == patient.id, CarePlan.institution_id == g.membership.institution_id)
                .order_by(CarePlan.id.desc()).limit(1)).mappings().first()
        plan = dict(row) if row else None
        if plan:
            plan['rules'] = {kind:plan[kind] for kind in ('check_in','contact_request') if plan[kind] is not None}
            audit('view_sensitive', 'check_in_instructions', plan['id'])
        instructions.append((patient, plan))
    db.session.commit()
    return render_template('medical/check_in.html', instructions=instructions)


@bp.post('/med/check-in')
@require_roles('patient')
def submit_check_in():
    patient = accessible_patient(request.form.get('patient_id', type=int))
    kind = request.form.get('kind')
    if kind not in ('check_in', 'contact_request') or request.form.get('monitoring_understood') != 'on':
        abort(400)
    reason = text_field('reason', 2000)
    db.session.execute(select(Patient.id).where(Patient.id == patient.id,
        Patient.institution_id == patient.institution_id).with_for_update())
    try:
        record_event(patient, kind, reason, 'patient:active')
        db.session.commit()
        flash('Your submission has been saved for review during the stated monitoring hours. It is not continuously monitored.', 'success')
    except ValueError as error:
        db.session.rollback()
        flash(str(error), 'error')
    except IntegrityError:
        db.session.rollback()
        flash('A submission is already being recorded. Please retry to add your message.', 'error')
    return redirect(url_for('med.check_in'))
