from datetime import date, timedelta
import secrets
from flask import render_template, request, redirect, url_for, abort, g, flash
from flask_login import current_user
from sqlalchemy import select, update
from extensions import db
from models import (Patient, Appointment, AppointmentProposal, CalendarBlock,
    CalendarDelegation, CalendarHistory, Membership, User)
from access import require_roles, accessible_patient, patient_scope, audit, audit_views
from medical_services import utcnow, parse_local, SERVICES
from scheduling_services import (available_slots, lock_doctor, propose, change,
    digest, history, expire_proposals, occupied_until)
from . import bp


def scoped_appointment(identity):
    from access import appointment_institution
    patient= db.session.scalar(patient_scope().where(Patient.id.in_(
        select(Appointment.patient_id).where(Appointment.id==identity))))
    if not patient:abort(404)
    lock_doctor(patient.doctor_id,patient.institution_id)
    row=db.session.scalar(select(Appointment).where(Appointment.id==identity,
        Appointment.patient_id==patient.id,Appointment.doctor_id==patient.doctor_id,
        appointment_institution(patient.institution_id)).with_for_update().execution_options(populate_existing=True))
    if not row:abort(404)
    return patient,row


@bp.get('/med/calendar')
@require_roles('dr','dr_assist','admin')
def calendar():
    from access import appointment_institution
    patients=list(db.session.scalars(patient_scope().order_by(Patient.name)))
    rows=list(db.session.scalars(select(Appointment).where(Appointment.patient_id.in_([p.id for p in patients]),
        Appointment.doctor_id.in_({p.doctor_id for p in patients}),
        appointment_institution(g.membership.institution_id)).order_by(Appointment.starts_at)))
    proposals=list(db.session.scalars(select(AppointmentProposal).where(AppointmentProposal.institution_id==g.membership.institution_id,
        AppointmentProposal.appointment_id.in_([a.id for a in rows])).order_by(AppointmentProposal.created_at.desc())))
    doctor_ids={p.doctor_id for p in patients}
    blocks=list(db.session.scalars(select(CalendarBlock).where(CalendarBlock.institution_id==g.membership.institution_id,
        CalendarBlock.doctor_id.in_(doctor_ids),CalendarBlock.reason=='administration')))
    activities=list(db.session.scalars(select(CalendarHistory).where(CalendarHistory.institution_id==g.membership.institution_id,
        CalendarHistory.appointment_id.in_([a.id for a in rows])).order_by(CalendarHistory.created_at.desc()).limit(100)))
    audit_views('appointment',rows)
    return render_template('medical/calendar.html',appointments=rows,patients=patients,proposals=proposals,
        blocks=blocks,now=utcnow(),slots=None,services=SERVICES,activities=activities)


@bp.get('/med/calendar/availability')
@require_roles('dr','dr_assist','admin')
def calendar_availability():
    from access import appointment_institution
    patient=accessible_patient(request.args.get('patient_id',type=int))
    try:
        day=date.fromisoformat(request.args.get('day',''))
        care=request.args.get('care_type','outpatient');kind=request.args.get('visit_kind','followup')
        exclude=request.args.get('appointment_id',type=int)
        if exclude:
            row=db.session.scalar(select(Appointment).where(Appointment.id==exclude,Appointment.patient_id==patient.id,
                appointment_institution(patient.institution_id)))
            if not row:abort(404)
            care=row.care_type or 'outpatient';kind=row.visit_kind or 'followup'
        slots=available_slots(patient,day,care,kind,exclude)
    except (ValueError,TypeError):abort(400)
    audit('view_availability','patient',patient.id);db.session.commit()
    return render_template('medical/available_times.html',slots=slots,patient=patient,day=day,care=care,kind=kind)


@bp.post('/med/calendar/<int:appointment_id>/propose')
@require_roles('dr','dr_assist','admin')
def calendar_propose(appointment_id):
    patient,row=scoped_appointment(appointment_id)
    try:
        propose(row,patient,parse_local(request.form.get('starts_at','')),
            request.form.get('version',type=int),request.form.get('reason','').strip())
        db.session.commit()
    except (ValueError,TypeError) as error:
        db.session.rollback();flash(str(error),'error')
    return redirect(url_for('med.calendar'))


@bp.post('/med/calendar/<int:appointment_id>/expire')
@require_roles('dr','dr_assist','admin')
def calendar_expire(appointment_id):
    patient,row=scoped_appointment(appointment_id)
    expire_proposals(row);db.session.commit()
    return redirect(url_for('med.calendar'))


@bp.route('/med/calendar/proposals/<proposal_key>/respond',methods=['GET','POST'])
@require_roles('patient')
def member_proposal(proposal_key):
    proposal=db.session.scalar(select(AppointmentProposal).where(AppointmentProposal.token_digest==proposal_key,
        AppointmentProposal.institution_id==g.membership.institution_id,
        AppointmentProposal.appointment_id.in_(select(Appointment.id).where(
            Appointment.patient_id.in_(patient_scope().with_only_columns(Patient.id))))))
    if not proposal:abort(404)
    patient,row=scoped_appointment(proposal.appointment_id)
    return respond(proposal,patient,row)


def respond(proposal,patient,row):
    if request.method=='POST':
        proposal=db.session.scalar(select(AppointmentProposal).where(AppointmentProposal.id==proposal.id).with_for_update().execution_options(populate_existing=True))
        if proposal.state!='pending':abort(409)
        if proposal.expires_at<=utcnow():
            expire_proposals(row);db.session.commit();abort(410)
        decision=request.form.get('decision')
        if decision not in ('accepted','declined'):abort(400)
        if proposal.base_version!=row.schedule_version:abort(409)
        if decision=='accepted':
            try:change(row,patient,proposal.proposed_at,proposal.base_version,proposal.reason,proposal)
            except ValueError as error:
                db.session.rollback();return render_template('medical/proposal_response.html',proposal=proposal,error=str(error),now=utcnow()),409
        else:
            proposal.state='declined';proposal.responded_at=utcnow()
            history(row,'proposal_declined',proposal=proposal)
        db.session.commit()
    return render_template('medical/proposal_response.html',proposal=proposal,now=utcnow())


@bp.route('/calendar-change/<token>',methods=['GET','POST'])
def guest_proposal(token):
    if len(token)>100:abort(404)
    proposal=db.session.scalar(select(AppointmentProposal).where(AppointmentProposal.token_digest==digest(token)))
    if not proposal:abort(404)
    # No appointment times or personal information before independent code verification.
    if request.method=='GET':return render_template('medical/guest_proposal.html')
    appointment=db.session.get(Appointment,proposal.appointment_id)
    if not appointment:abort(404)
    patient=db.session.get(Patient,appointment.patient_id)
    if (not patient or patient.user_id or patient.institution_id!=proposal.institution_id or
            appointment.institution_id not in (None, patient.institution_id) or
            appointment.doctor_id!=patient.doctor_id):abort(404)
    lock_doctor(appointment.doctor_id,proposal.institution_id)
    db.session.refresh(appointment);db.session.refresh(proposal)
    if proposal.expires_at<=utcnow() or proposal.state!='pending':abort(410)
    if proposal.verification_attempts>=5:abort(429)
    from coordination_services import latest_decision, verified_communication_allowed
    # Withdrawal/destination changes invalidate optional guest delivery at response time too.
    decision = latest_decision(patient.id, 'administrative_contact', 'email',
                               institution_id=proposal.institution_id)
    if not verified_communication_allowed(decision) or decision.id != proposal.communication_decision_id:
        abort(403)
    proposal.verification_attempts+=1
    if not secrets.compare_digest(digest(request.form.get('code','')),proposal.code_digest):
        db.session.commit();abort(403)
    db.session.flush()
    if request.form.get('decision')=='review':
        db.session.commit()
        return render_template('medical/proposal_response.html',proposal=proposal,now=utcnow())
    return respond(proposal,patient,appointment)


@bp.post('/med/calendar/delegations')
@require_roles('dr')
def calendar_delegate():
    assistant=request.form.get('assistant_id',type=int)
    member=db.session.scalar(select(Membership).join(User,User.id==Membership.user_id).where(
        Membership.user_id==assistant,Membership.institution_id==g.membership.institution_id,
        Membership.role=='dr_assist',Membership.enabled.is_(True),User.enabled.is_(True),
        Membership.supervising_doctor_id==current_user.id))
    if not member:abort(404)
    lock_doctor(current_user.id,g.membership.institution_id)
    try:expires=parse_local(request.form.get('expires_at',''))
    except (ValueError,TypeError):abort(400)
    if expires<=utcnow() or expires>utcnow()+timedelta(days=366):abort(400)
    row=db.session.scalar(select(CalendarDelegation).where(CalendarDelegation.institution_id==g.membership.institution_id,
        CalendarDelegation.doctor_id==current_user.id,CalendarDelegation.assistant_id==assistant))
    if not row:
        row=CalendarDelegation(institution_id=g.membership.institution_id,doctor_id=current_user.id,assistant_id=assistant)
        db.session.add(row)
    row.enabled=request.form.get('enabled')=='yes';row.expires_at=expires
    db.session.flush();audit('delegate_admin_blocks' if row.enabled else 'revoke_admin_blocks','calendar_delegation',row.id)
    db.session.commit();return redirect(url_for('med.calendar'))


def block_permission(doctor_id):
    if doctor_id not in [p.doctor_id for p in db.session.scalars(patient_scope())]:abort(404)
    lock_doctor(doctor_id,g.membership.institution_id)
    if g.membership.role=='dr_assist':
        permission=db.session.scalar(select(CalendarDelegation.id).where(CalendarDelegation.institution_id==g.membership.institution_id,
            CalendarDelegation.doctor_id==doctor_id,CalendarDelegation.assistant_id==current_user.id,
            CalendarDelegation.enabled.is_(True),CalendarDelegation.expires_at>utcnow()))
        if not permission:abort(403)


@bp.post('/med/calendar/blocks')
@require_roles('dr','dr_assist')
def calendar_block():
    doctor=request.form.get('doctor_id',type=int);block_permission(doctor)
    try:start=parse_local(request.form.get('starts_at',''));end=parse_local(request.form.get('ends_at',''))
    except (TypeError,ValueError):abort(400)
    if start<=utcnow() or end<=start or end-start>timedelta(days=1):abort(400)
    candidates=db.session.scalars(select(Appointment).where(Appointment.doctor_id==doctor,
        (Appointment.institution_id==g.membership.institution_id) | Appointment.patient_id.in_(
            select(Patient.id).where(Patient.institution_id==g.membership.institution_id)),
        Appointment.status.in_(('scheduled','held')),Appointment.starts_at<end))
    collision=any(occupied_until(a)>start for a in candidates
        if a.status!='held' or a.hold_expires_at is None or a.hold_expires_at>utcnow())
    if collision:abort(409)
    row=CalendarBlock(institution_id=g.membership.institution_id,doctor_id=doctor,starts_at=start,ends_at=end,
        reason='administration',created_by=current_user.id)
    db.session.add(row);db.session.flush()
    db.session.add(CalendarHistory(institution_id=row.institution_id,block_id=row.id,actor_id=current_user.id,action='admin_block_created',original_at=start,new_at=end))
    audit('create_admin_block','calendar_block',row.id);db.session.commit();return redirect(url_for('med.calendar'))


@bp.post('/med/calendar/blocks/<int:block_id>/release')
@require_roles('dr','dr_assist')
def calendar_release_block(block_id):
    row=db.session.scalar(select(CalendarBlock).where(CalendarBlock.id==block_id,
        CalendarBlock.institution_id==g.membership.institution_id,CalendarBlock.reason=='administration'))
    if not row:abort(404)
    block_permission(row.doctor_id)
    db.session.refresh(row)
    if row.starts_at<=utcnow() or not row.enabled:abort(409)
    # Assistants may release only administrative blocks they themselves created.
    if g.membership.role=='dr_assist' and row.created_by!=current_user.id:abort(403)
    row.enabled=False;row.released_by=current_user.id;row.released_at=utcnow()
    db.session.add(CalendarHistory(institution_id=row.institution_id,block_id=row.id,actor_id=current_user.id,action='admin_block_released'))
    audit('release_admin_block','calendar_block',row.id);db.session.commit();return redirect(url_for('med.calendar'))
