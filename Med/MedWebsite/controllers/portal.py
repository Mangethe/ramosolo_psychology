from datetime import datetime, time, timedelta, timezone
from flask import render_template, request, redirect, url_for, flash, g, abort
from flask_login import current_user, login_required
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from extensions import db
from models import Patient, Appointment, Admission, Membership, CareAssignment, User
from access import (appointment_assignment, appointment_institution, require_roles, require_capability, patient_scope,
                    accessible_patient, audit, audit_views, ROLE_MATRIX)
from medical_services import SERVICES, utcnow, parse_local, statistics, doctors, TZ
from . import bp
from continuity_services import current_plan, record_event, archive_events

ALL = tuple(ROLE_MATRIX)
STAFF = tuple(role for role, permissions in ROLE_MATRIX.items() if 'operational' in permissions)
SCHEDULERS = tuple(role for role, permissions in ROLE_MATRIX.items() if 'schedule' in permissions)
DASHBOARD_PERIODS = ((1, 'Today'), (7, '7 days'), (14, '14 days'))


def locked_appointment(appointment_id):
    """Serialize appointment changes and continuity submissions on their scoped patient."""
    patient = db.session.scalar(patient_scope().where(Patient.id.in_(
        select(Appointment.patient_id).where(Appointment.id == appointment_id))).with_for_update())
    if not patient:
        abort(404)
    appointment = db.session.scalar(select(Appointment).where(
        Appointment.id == appointment_id, Appointment.patient_id == patient.id,
        appointment_institution(patient.institution_id)).with_for_update())
    if not appointment:
        abort(404)
    return patient, appointment


@bp.get('/med')
@login_required
def dashboard():
    if not g.membership or g.membership.institution.kind != 'medical':
        return render_template('institutions/unavailable.html')
    now = utcnow()
    today = now.replace(tzinfo=timezone.utc).astimezone(TZ).date()
    period = request.args.get('period', default=7, type=int)
    if period not in {days for days, _ in DASHBOARD_PERIODS}:
        period = 7
    days = [today + timedelta(days=offset) for offset in range(period)]
    boundaries = [datetime.combine(day, time.min, TZ).astimezone(timezone.utc).replace(tzinfo=None)
                  for day in (*days, today + timedelta(days=period))]
    requested_day = request.args.get('day')
    selected = next((index for index, day in enumerate(days) if day.isoformat() == requested_day), None)

    scope = patient_scope()
    upcoming = select(Appointment).where(Appointment.patient_id.in_(scope.with_only_columns(Patient.id)),
        appointment_institution(g.membership.institution_id), appointment_assignment(), Appointment.status == 'scheduled',
        Appointment.starts_at >= now)
    # SQL returns counts per Johannesburg day without exporting appointment records for the chart.
    bucket = case(*[(Appointment.starts_at < end, index) for index, end in enumerate(boundaries[1:-1])],
                  else_=period - 1) if period > 1 else None
    within_period = upcoming.where(Appointment.starts_at < boundaries[-1])
    if bucket is None:
        counts = {0: db.session.scalar(within_period.with_only_columns(func.count(Appointment.id)))}
    else:
        counts = dict(db.session.execute(within_period.with_only_columns(bucket.label('day_bucket'),
            func.count(Appointment.id)).group_by('day_bucket')).all())
    chart = [(day, counts.get(index, 0)) for index, day in enumerate(days)]
    if selected is not None:
        within_period = within_period.where(Appointment.starts_at >= boundaries[selected],
                                            Appointment.starts_at < boundaries[selected + 1])
    appointments = list(db.session.scalars(within_period.order_by(Appointment.starts_at, Appointment.id).limit(8)))
    is_patient = g.membership.role == 'patient'
    next_appointment = db.session.scalar(upcoming.order_by(Appointment.starts_at, Appointment.id).limit(1)) if is_patient else None
    stats = None if is_patient else statistics(list(db.session.scalars(scope)),
        now=now, include_admissions=g.membership.role != 'dr_assist', appointment_filter=appointment_assignment())[0]
    viewed = {appointment.id: appointment for appointment in appointments}
    if next_appointment:
        viewed[next_appointment.id] = next_appointment
    audit_views('appointment', viewed.values())
    titles = {'dr': 'Your practice, at a glance', 'nurse': 'Your care dashboard',
              'dr_assist': 'Keep the day running smoothly', 'admin': 'Your practice overview',
              'patient': 'A little clarity for your next step'}
    return render_template('medical/dashboard.html', stats=stats, appointments=appointments,
        next_appointment=next_appointment, title=titles[g.membership.role], now=now,
        periods=DASHBOARD_PERIODS, period=period, selected_day=days[selected] if selected is not None else None,
        chart=chart, chart_max=max(1, max(count for _, count in chart)), chart_total=sum(counts.values()),
        list_total=counts.get(selected, 0) if selected is not None else sum(counts.values()))


@bp.get('/med/patients')
@require_roles(*STAFF)
def patients():
    rows = list(db.session.scalars(patient_scope().order_by(Patient.name)))
    _, latest, admitted = statistics(rows, include_admissions=g.membership.role != 'dr_assist',
                                     appointment_filter=appointment_assignment())
    q = request.args.get('q', '').strip().lower()[:100]
    if q:
        rows = [p for p in rows if q in p.name.lower() or q in (p.email or '').lower()]
    audit_views('patient', rows)
    return render_template('medical/patients.html', patients=rows, latest=latest,
        admitted=admitted, now=utcnow(), cutoff=utcnow()-timedelta(days=90), q=q,
        doctors=doctors(g.membership.institution_id))


@bp.post('/med/patients')
@require_roles(*SCHEDULERS)
def create_patient():
    permitted = doctors(g.membership.institution_id)
    selected = request.form.get('doctor_id', type=int)
    if g.membership.role == 'dr':
        selected = current_user.id
    elif g.membership.role == 'dr_assist':
        selected = g.membership.supervising_doctor_id
    if selected not in [d.id for d in permitted]:
        abort(400)
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    if not 2 <= len(name) <= 120 or len(email) > 254 or len(phone) > 40:
        abort(400)
    patient = Patient(institution_id=g.membership.institution_id, doctor_id=selected,
        name=name, email=email, phone=phone)
    db.session.add(patient)
    db.session.flush()
    audit('create', 'patient', patient.id)
    db.session.commit()
    flash('Patient added. A portal account can be linked by an administrator.', 'success')
    return redirect(url_for('med.patients'))


@bp.get('/med/patients/<int:patient_id>')
@require_roles(*STAFF)
def patient_detail(patient_id):
    patient = accessible_patient(patient_id)
    appointments = list(db.session.scalars(select(Appointment).where(
        Appointment.patient_id == patient.id, appointment_institution(patient.institution_id), appointment_assignment())
        .order_by(Appointment.starts_at.desc())))

    admissions = [] if g.membership.role == 'dr_assist' else list(db.session.scalars(select(Admission).where(
        Admission.patient_id == patient.id).order_by(Admission.admitted_at.desc())))
    audit('view', 'patient', patient.id)
    db.session.commit()
    nurses = list(db.session.scalars(select(User).join(Membership, Membership.user_id == User.id).where(
        Membership.institution_id == g.membership.institution_id, Membership.role == 'nurse',
        Membership.enabled.is_(True), User.enabled.is_(True))))
    assigned = set(db.session.scalars(select(CareAssignment.nurse_id).where(CareAssignment.patient_id == patient.id)))
    return render_template('medical/patient.html', patient=patient, appointments=appointments,
        admissions=admissions, nurses=nurses, assigned=assigned)


@bp.post('/med/patients/<int:patient_id>/care-team')
@require_roles('dr', 'admin')
def assign_nurse(patient_id):
    patient = accessible_patient(patient_id)
    nurse_id = request.form.get('nurse_id', type=int)
    member = db.session.scalar(select(Membership).where(Membership.user_id == nurse_id,
        Membership.institution_id == g.membership.institution_id, Membership.role == 'nurse', Membership.enabled.is_(True)))
    if not member:
        abort(400)
    existing = db.session.scalar(select(CareAssignment).where(
        CareAssignment.patient_id == patient.id, CareAssignment.nurse_id == nurse_id))
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(CareAssignment(patient_id=patient.id, nurse_id=nurse_id))
    audit('change_care_assignment', 'patient', patient.id)
    db.session.commit()
    return redirect(url_for('med.patient_detail', patient_id=patient.id))


@bp.get('/med/appointments')
@require_roles(*ALL)
def appointments():
    query = select(Appointment).where(Appointment.patient_id.in_(patient_scope().with_only_columns(Patient.id)),
        appointment_institution(g.membership.institution_id), appointment_assignment())
    rows = list(db.session.scalars(query.order_by(Appointment.starts_at.desc())))
    audit_views('appointment', rows)
    proposals = []
    if g.membership.role == 'patient':
        from models import AppointmentProposal
        proposals = db.session.execute(select(AppointmentProposal.id, AppointmentProposal.proposed_at,
            AppointmentProposal.state).where(AppointmentProposal.institution_id == g.membership.institution_id,
            AppointmentProposal.appointment_id.in_([a.id for a in rows]))).all()
    return render_template('medical/appointments.html', appointments=rows, proposals=proposals)
@bp.post('/med/appointments')
@require_roles(*SCHEDULERS)
def create_appointment():
    patient = accessible_patient(request.form.get('patient_id', type=int))
    from scheduling_services import lock_doctor, validate_slot, history
    lock_doctor(patient.doctor_id,patient.institution_id)
    try:
        starts=parse_local(request.form.get('starts_at',''))
        care = request.form.get('care_type', 'outpatient')
        kind = request.form.get('visit_kind', 'followup')
        service=request.form.get('service','')
        if service not in SERVICES:raise ValueError('Choose a listed service.')
        slot=validate_slot(patient,starts,care,kind)
        # The live booking guard names the follow-up slot kind "routine".
        # Keep the existing form/API value but persist the live-schema value.
        stored_kind='routine' if kind=='followup' else kind
        appointment=Appointment(institution_id=patient.institution_id,patient_id=patient.id,doctor_id=patient.doctor_id,starts_at=starts,
            ends_at=slot[1],occupied_until=slot[2],care_type=care,visit_kind=stored_kind,service=service,status='scheduled')
        db.session.add(appointment);db.session.flush()
        history(appointment,'scheduled',new=starts)
        from scheduling_services import refresh_reminders
        refresh_reminders(appointment)
        from appointment_email import queue
        queue(appointment, 'appt_confirmed')
        audit('schedule','appointment',appointment.id);db.session.commit()
        flash('Appointment scheduled. In-app reminders use the confirmed time.','success')
    except (ValueError,TypeError,IntegrityError) as error:
        db.session.rollback()
        flash(str(error) if isinstance(error,ValueError) else 'This slot is unavailable.','error')
    return redirect(url_for('med.appointments'))


@bp.post('/med/appointments/<int:appointment_id>/status')
@require_roles(*SCHEDULERS)
def appointment_status(appointment_id):
    from .calendar import scoped_appointment
    patient, appointment = scoped_appointment(appointment_id)
    status = request.form.get('status')
    if status not in ('scheduled', 'completed', 'cancelled', 'no_show'):
        abort(400)
    if g.membership.role == 'dr_assist' and (status != 'cancelled' or appointment.status != 'scheduled' or appointment.starts_at <= utcnow()):
        abort(403)
    if status in ('completed', 'no_show') and appointment.starts_at > utcnow():
        flash('A future appointment cannot be marked completed or missed.', 'error')
        return redirect(url_for('med.appointments'))
    if status in ('scheduled','cancelled') and appointment.status!=status:
        if request.form.get('version',type=int)!=appointment.schedule_version:abort(409)
        if status=='scheduled':abort(403)  # use the shared booking engine to create a new booking
    old_status = appointment.status
    appointment.status = status
    if old_status!=status:
        from scheduling_services import history, pending_proposals, refresh_reminders
        appointment.schedule_version+=1
        history(appointment,'status_'+status,old=appointment.starts_at,reason=request.form.get('reason','')[:240])
        if status=='cancelled':
            for proposal in db.session.scalars(pending_proposals(appointment)):
                proposal.state='superseded';proposal.responded_at=utcnow()
            refresh_reminders(appointment)
    try:
        db.session.flush()
        if status != old_status:
            from appointment_email import queue
            queue(appointment, 'appt_cancelled' if status == 'cancelled' else None)
        if status == 'no_show':
            plan = current_plan(patient)
            if plan and 'missed_appointment' in plan.rules:
                try:
                    record_event(patient, 'missed_appointment', 'Appointment marked missed by staff.',
                                 'appointment:%s' % appointment.id, appointment)
                except ValueError as error:
                    flash(str(error), 'error')
        elif status != old_status:
            archive_events(patient, ('missed_appointment', 'unconfirmed_booking', 'failed_reminder'),
                           'Appointment status updated to %s.' % status, appointment.id)
        audit('status_'+status, 'appointment', appointment.id)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash('This slot is already booked.', 'error')
    return redirect(url_for('med.appointments'))


@bp.post('/med/appointments/<int:appointment_id>/reschedule')
@require_roles(*SCHEDULERS)
def reschedule_appointment(appointment_id):
    from .calendar import scoped_appointment
    from scheduling_services import change
    patient, appointment = scoped_appointment(appointment_id)
    # Direct changes require explicit staff confirmation; ordinary suggestions are proposals.
    if request.form.get('confirmed')!='yes':abort(400)
    reason=request.form.get('reason','').strip()
    if not reason or len(reason)>240:abort(400)
    try:
        change(appointment,patient,parse_local(request.form.get('starts_at','')),
            request.form.get('version',type=int),reason)
        audit('reschedule','appointment',appointment.id);db.session.commit()
    except (ValueError,TypeError,IntegrityError):
        db.session.rollback();flash('This slot is unavailable. The original appointment was preserved.','error')
    return redirect(url_for('med.calendar'))


@bp.get('/med/admissions')
@require_capability('admissions')
def admissions():
    patients = list(db.session.scalars(patient_scope().order_by(Patient.name)))
    rows = list(db.session.scalars(select(Admission).where(Admission.patient_id.in_(
        [p.id for p in patients])).order_by(Admission.admitted_at.desc())))
    audit_views('admission', rows)
    return render_template('medical/admissions.html', admissions=rows, patients=patients)


@bp.post('/med/admissions')
@require_roles('dr', 'nurse', 'admin')
def admit():
    patient = accessible_patient(request.form.get('patient_id', type=int))
    facility = request.form.get('facility', '').strip()
    if not 2 <= len(facility) <= 120:
        abort(400)
    row = Admission(patient_id=patient.id, facility=facility, admitted_at=utcnow())
    db.session.add(row)
    try:
        db.session.flush()
        audit('admit', 'admission', row.id)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash('This patient already has an open admission.', 'error')
    return redirect(url_for('med.admissions'))


@bp.post('/med/admissions/<int:admission_id>/discharge')
@require_roles('dr', 'nurse', 'admin')
def discharge(admission_id):
    row = db.session.scalar(select(Admission).where(Admission.id==admission_id,
        Admission.patient_id.in_(patient_scope().with_only_columns(Patient.id))))
    if not row:
        abort(404)
    if not row:
        abort(404)
    patient=accessible_patient(row.patient_id)
    from coordination_services import lock_patient, ensure_discharge, record_history
    lock_patient(patient.id)
    row=db.session.scalar(select(Admission).where(Admission.id==admission_id,
        Admission.patient_id==patient.id).with_for_update().execution_options(populate_existing=True))
    if row.discharged_at is None:
        row.discharged_at = utcnow()
        followup=ensure_discharge(row,patient)
        if followup.due_at and followup.due_at<row.discharged_at:
            followup.planning_complete=False
        record_history('discharge_followup',followup,'actual_discharge_recorded')
        audit('discharge', 'admission', row.id)
        db.session.commit()
    return redirect(url_for('med.admissions'))
