from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from extensions import db
from models import User, Institution, Membership, Patient, BookingRequest, AuditEvent, ROLES
from access import require_roles, require_capability, audit, patient_scope
from medical_services import doctors
from account_verification import issue, valid_address, welcome_if_active

bp = Blueprint('admin', __name__)


@bp.route('/institutions', methods=['GET', 'POST'])
@login_required
def institutions():
    if request.method == 'POST':
        selected = request.form.get('institution_id', type=int)
        if selected not in [m.institution_id for m in g.memberships]:
            abort(403)
        from portal_sessions import rotate
        if not rotate(current_user, selected):
            return redirect(url_for('auth.login'))
        return redirect(url_for('med.dashboard'))
    return render_template('institutions/index.html')


@bp.route('/admin/users', methods=['GET', 'POST'])
@require_capability('accounts')
def users():
    institution_id = g.membership.institution_id
    med_doctors = doctors(institution_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', '')
        doctor_id = request.form.get('doctor_id', type=int)
        patient_id = request.form.get('patient_id', type=int)
        if not 2 <= len(name) <= 120 or not valid_address(email) or not 12 <= len(password) <= 128 or role not in ROLES:
            flash('Check the name, email, role and a password of 12–128 characters.', 'error')
            return redirect(url_for('admin.users'))
        if role in ('patient', 'dr_assist') and doctor_id not in [d.id for d in med_doctors]:
            abort(400)
        patient = None
        if role == 'patient' and patient_id:
            patient = db.session.scalar(patient_scope().where(Patient.id == patient_id).with_for_update()
                                        .execution_options(populate_existing=True))
            if not patient:
                abort(404)
            if patient.user_id or patient.doctor_id != doctor_id:
                abort(400)
        # Existing accounts cannot be claimed or have their password reset by another institution.
        if db.session.scalar(select(User.id).where(User.email == email)):
            flash('This account already exists. Use the owner CLI to add a verified institution membership.', 'error')
            return redirect(url_for('admin.users'))
        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        member = Membership(user_id=user.id, institution_id=institution_id, role=role,
            supervising_doctor_id=doctor_id if role == 'dr_assist' else None)
        db.session.add(member)
        if role == 'patient':
            if patient:
                patient.user_id = user.id
            else:
                db.session.add(Patient(institution_id=institution_id, user_id=user.id,
                    doctor_id=doctor_id, name=name, email=email))
        audit('create_account', 'user', user.id)
        issue(user, email, initial=True)
        try:
            db.session.commit()
            flash('Account created. Email confirmation is required before sign-in.', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('The account could not be created. Check for duplicate records.', 'error')
        return redirect(url_for('admin.users'))
    members = list(db.session.scalars(select(Membership).where(
        Membership.institution_id == institution_id).order_by(Membership.id)))
    patients = list(db.session.scalars(select(Patient).where(
        Patient.institution_id == institution_id, Patient.user_id.is_(None)).order_by(Patient.name)))
    return render_template('users/index.html', members=members, doctors=med_doctors, patients=patients)


@bp.post('/admin/users/<int:member_id>/toggle')
@require_capability('accounts')
def toggle_member(member_id):
    member = db.session.scalar(select(Membership).where(Membership.id == member_id,
        Membership.institution_id == g.membership.institution_id))
    if not member:
        abort(404)
    if member.user_id == current_user.id:
        abort(400)
    user = db.session.get(User, member.user_id, with_for_update=True, populate_existing=True)
    db.session.refresh(member, with_for_update=True)
    if member.institution_id != g.membership.institution_id:
        abort(404)
    member.enabled = not member.enabled
    user.session_version += 1
    if member.enabled:
        welcome_if_active(user)
    audit('toggle_membership', 'membership', member.id)
    db.session.commit()
    return redirect(url_for('admin.users'))


@bp.get('/admin/requests')
@require_roles('admin')
def requests_queue():
    rows = list(db.session.scalars(select(BookingRequest).where(
        BookingRequest.institution_id == g.membership.institution_id).order_by(BookingRequest.id.desc())))
    return render_template('appointments/requests.html', requests=rows)


@bp.post('/admin/requests/<int:request_id>/review')
@require_roles('admin')
def review_request(request_id):
    row = db.session.scalar(select(BookingRequest).where(BookingRequest.id == request_id,
        BookingRequest.institution_id == g.membership.institution_id))
    if not row:
        abort(404)
    row.status = 'reviewed'
    audit('review', 'booking_request', row.id)
    db.session.commit()
    flash('Request marked reviewed. Contact the requester; schedule a confirmed appointment separately.', 'success')
    return redirect(url_for('admin.requests_queue'))


@bp.get('/admin/audit')
@require_roles('admin')
def audit_log():
    rows = list(db.session.scalars(select(AuditEvent).where(
        AuditEvent.institution_id == g.membership.institution_id).order_by(AuditEvent.id.desc()).limit(200)))
    return render_template('admin/audit.html', events=rows)
