from datetime import timedelta
from flask import render_template, request, redirect, url_for, flash, g, abort
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from extensions import db
from models import Patient, Appointment, Admission, Membership, CareAssignment, User
from access import require_roles, patient_scope, accessible_patient, audit
from medical_services import SERVICES, utcnow, parse_local, statistics, doctors, TZ
from . import bp

ALL = ('dr', 'nurse', 'admin', 'dr_assist', 'patient')
STAFF = ('dr', 'nurse', 'admin', 'dr_assist')
SCHEDULERS = ('dr', 'admin', 'dr_assist')


@bp.get('/med')
@login_required
def dashboard():
    if not g.membership or g.membership.institution.kind != 'medical':
        return render_template('institutions/unavailable.html')
    patients = list(db.session.scalars(patient_scope().order_by(Patient.name)))
    stats, latest, admitted = statistics(patients)
    ids = [p.id for p in patients]
    now = utcnow()
    appointments = list(db.session.scalars(select(Appointment).where(Appointment.patient_id.in_(ids),
        Appointment.status == 'scheduled', Appointment.starts_at >= now).order_by(Appointment.starts_at).limit(8)))
    reminders = [a for a in appointments if a.starts_at <= now + timedelta(days=7)]
    titles = {'dr': 'Your practice, at a glance', 'nurse': 'Your care dashboard',
              'dr_assist': 'Keep the day running smoothly', 'admin': 'Your practice overview',
              'patient': 'A little clarity for your next step'}
    return render_template('medical/dashboard.html', stats=stats, appointments=appointments,
        reminders=reminders, title=titles[g.membership.role], now=now, services=SERVICES)


@bp.get('/med/patients')
@require_roles(*STAFF)
def patients():
    rows = list(db.session.scalars(patient_scope().order_by(Patient.name)))
    stats, latest, admitted = statistics(rows)
    q = request.args.get('q', '').strip().lower()[:100]
    if q:
        rows = [p for p in rows if q in p.name.lower() or q in (p.email or '').lower()]
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
        Appointment.patient_id == patient.id).order_by(Appointment.starts_at.desc())))
    admissions = list(db.session.scalars(select(Admission).where(
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
    patients = list(db.session.scalars(patient_scope().order_by(Patient.name)))
    query = select(Appointment).where(Appointment.patient_id.in_([p.id for p in patients]))
    rows = list(db.session.scalars(query.order_by(Appointment.starts_at.desc())))
    return render_template('medical/appointments.html', appointments=rows, patients=patients, services=SERVICES)


@bp.post('/med/appointments')
@require_roles(*SCHEDULERS)
def create_appointment():
    patient = accessible_patient(request.form.get('patient_id', type=int))
    try:
        starts = parse_local(request.form.get('starts_at', ''))
        if starts <= utcnow() or starts.minute != 0 or starts.second != 0:
            raise ValueError()
        service = request.form.get('service', '')
        if service not in SERVICES:
            raise ValueError()
    except (ValueError, TypeError):
        flash('Choose a future date, an hourly slot (e.g. 10:00), and a listed service.', 'error')
        return redirect(url_for('med.appointments'))
    appointment = Appointment(patient_id=patient.id, doctor_id=patient.doctor_id,
        starts_at=starts, service=service, status='scheduled')
    db.session.add(appointment)
    try:
        db.session.flush()
        audit('schedule', 'appointment', appointment.id)
        db.session.commit()
        flash('Appointment scheduled. An in-app reminder appears during the preceding seven days.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('That patient or doctor already has this slot. Choose another time.', 'error')
    return redirect(url_for('med.appointments'))


@bp.post('/med/appointments/<int:appointment_id>/status')
@require_roles(*SCHEDULERS)
def appointment_status(appointment_id):
    appointment = db.session.get(Appointment, appointment_id)
    if not appointment:
        abort(404)
    accessible_patient(appointment.patient_id)
    status = request.form.get('status')
    if status not in ('scheduled', 'completed', 'cancelled', 'no_show'):
        abort(400)
    if g.membership.role == 'dr_assist' and (status not in ('scheduled', 'cancelled') or appointment.status in ('completed', 'no_show')):
        abort(403)
    if status in ('completed', 'no_show') and appointment.starts_at > utcnow():
        flash('A future appointment cannot be marked completed or missed.', 'error')
        return redirect(url_for('med.appointments'))
    appointment.status = status
    try:
        audit('status_'+status, 'appointment', appointment.id)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash('This slot is already booked.', 'error')
    return redirect(url_for('med.appointments'))


@bp.get('/med/admissions')
@require_roles(*STAFF)
def admissions():
    patients = list(db.session.scalars(patient_scope().order_by(Patient.name)))
    rows = list(db.session.scalars(select(Admission).where(Admission.patient_id.in_(
        [p.id for p in patients])).order_by(Admission.admitted_at.desc())))
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
    row = db.session.get(Admission, admission_id)
    if not row:
        abort(404)
    accessible_patient(row.patient_id)
    if row.discharged_at is None:
        row.discharged_at = utcnow()
        audit('discharge', 'admission', row.id)
        db.session.commit()
    return redirect(url_for('med.admissions'))
