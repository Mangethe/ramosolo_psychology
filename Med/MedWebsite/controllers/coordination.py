from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import csv
import io
import secrets
from flask import abort, g, request, render_template, redirect, url_for, Response, flash
from flask_login import current_user
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from extensions import db
from access import (require_roles, require_capability, accessible_patient, patient_scope, appointment_assignment, appointment_institution,
                    can_patient, audit, audit_views)
from models import (Patient, Admission, CarePlan, DischargeFollowup, Referral, ReferralClinical,
    CommunicationDecision, CareReview, CareReviewSignoff, CoordinationHistory, CoordinationPolicy,
    ExternalPractitioner, Appointment)
from models import CoordinationCoverage, Membership, User
from medical_services import utcnow, parse_local
from coordination_services import (PURPOSES, CHANNELS, REFERRAL_TRANSITIONS, lock_patient,
    staff_team, validate_owner, latest_policy, record_history, ensure_discharge, ensure_review,
    source_row, source_scope, touch, suppress_unsent, recheck_queued, communication_allowed,
    latest_decision, action_items, legacy_table, coordination_patient_scope, coordination_patient)
from . import bp

STAFF=('dr','nurse','dr_assist','admin')


@bp.errorhandler(IntegrityError)
def coordination_conflict(error):
    from werkzeug.exceptions import Conflict
    db.session.rollback()
    return render_template('errors/error.html',error=Conflict('A conflicting update was rejected. Reload the source record.')),409


def text(name,limit=1500,required=True):
    value=request.form.get(name,'').strip()
    if (required and not value) or len(value)>limit:abort(400)
    return value


def date(name,required=False):
    value=request.form.get(name,'').strip()
    if not value:
        if required:abort(400)
        return None
    try:return parse_local(value)
    except (ValueError,TypeError,OverflowError):abort(400)


def no_files():
    if request.files:abort(400)


def operational_change(row,kind,patient,clinical_only=False,doctor_only=False):
    previous=row.owner_id
    prior_cover=row.cover_id
    owner=request.form.get('owner_id',type=int)
    cover=request.form.get('cover_id',type=int)
    workflow={'discharge_followup':'discharge','care_review':'review','referral':'referral'}.get(kind)
    validate_owner(patient,owner,clinical_only,doctor_only,workflow)
    validate_owner(patient,cover,clinical_only,False,workflow)
    row.owner_id=owner;row.cover_id=cover
    row.owner_unavailable=request.form.get('owner_unavailable')=='on'
    row.due_at=date('due_at')
    if previous!=owner:record_history(kind,row,'owner_changed',previous)
    record_history(kind,row,'assignment_updated',previous,previous_cover=prior_cover)


def history(kind,identity):
    return list(db.session.scalars(select(CoordinationHistory).where(
        CoordinationHistory.institution_id==g.membership.institution_id,
        CoordinationHistory.source_type==kind,CoordinationHistory.source_id==identity)
        .order_by(CoordinationHistory.id)))


@bp.route('/med/coordination/policies',methods=['GET','POST'])
@require_roles(*STAFF)
def coordination_policies():
    if request.method=='POST':
        no_files()
        if g.membership.role!='dr':abort(403)
        kind=request.form.get('kind')
        hours=request.form.get('deadline_hours',type=int);soon=request.form.get('due_soon_days',type=int)
        if kind not in ('discharge','review') or not hours or not 1<=hours<=8760 or soon is None or not 0<=soon<=365 or request.form.get('approved')!='on':abort(400)
        # Serialize policy numbering on the institution row.
        from models import Institution
        db.session.execute(select(Institution.id).where(Institution.id==g.membership.institution_id).with_for_update())
        prior=latest_policy(kind)
        row=CoordinationPolicy(institution_id=g.membership.institution_id,kind=kind,
            version=prior.version+1 if prior else 1,deadline_hours=hours,due_soon_days=soon,
            instructions=text('instructions'),approved_by_id=current_user.id)
        db.session.add(row);db.session.flush();audit('approve_coordination_policy','coordination_policy',row.id)
        db.session.commit();return redirect(url_for('med.coordination_policies'))
    policies=list(db.session.scalars(select(CoordinationPolicy).where(
        CoordinationPolicy.institution_id==g.membership.institution_id).order_by(CoordinationPolicy.id.desc())))
    return render_template('medical/coordination/policies.html',policies=policies)


@bp.route('/med/admissions/<int:admission_id>/follow-up',methods=['GET','POST'])
@require_roles('dr','nurse','admin')
def discharge_followup(admission_id):
    admission=db.session.scalar(select(Admission).where(Admission.id==admission_id,
        Admission.patient_id.in_(coordination_patient_scope('discharge').with_only_columns(Patient.id))))
    if not admission:abort(404)
    patient=coordination_patient(admission.patient_id,'discharge')
    row=db.session.scalar(select(DischargeFollowup).where(DischargeFollowup.admission_id==admission.id,
        DischargeFollowup.institution_id==patient.institution_id))
    if g.membership.role=='nurse' and (not row or current_user.id not in (row.owner_id,row.cover_id)):abort(404)
    if request.method=='POST':
        no_files();lock_patient(patient.id,'discharge')
        row=ensure_discharge(admission,patient)
        row=db.session.scalar(select(DischargeFollowup).where(DischargeFollowup.id==row.id).with_for_update().execution_options(populate_existing=True))
        if g.membership.role=='nurse' and current_user.id not in (row.owner_id,row.cover_id):abort(404)
        touch(row,request.form.get('version',type=int))
        action=request.form.get('action')
        if row.status in ('completed','cancelled'):abort(409)
        if action in ('assign','approve_planning'):
            if g.membership.role not in ('dr','admin'):abort(403)
            if action=='approve_planning' and g.membership.role!='dr':abort(403)
            row.planning_complete=False
            operational_change(row,'discharge_followup',patient,clinical_only=True)
            row.team=text('team',120,False)
            policy=latest_policy('discharge')
            row.policy_id=policy.id if policy else None
            if policy and row.due_at is None and row.owner_id:
                row.due_at=(admission.discharged_at or utcnow())+timedelta(hours=policy.deadline_hours)
            # Changing ownership/date invalidates the prior planning sign-off.
            row.planning_complete=False
            if action=='approve_planning':
                if g.membership.role!='dr':abort(403)
                if not row.owner_id or not row.due_at or not row.policy_id:abort(400)
                row.planning_complete=True
            if g.membership.role=='dr':
                row.patient_visible=request.form.get('patient_visible')=='on'
                row.agreed_action=text('agreed_action',1000,row.patient_visible)
        elif action=='contact_attempt':
            if g.membership.role=='admin':abort(403)
            outcome=request.form.get('contact_outcome')
            if outcome not in ('no_answer','neutral_message','reached','successful_contact'):abort(400)
            if outcome in ('reached','successful_contact'):row.status='contacted'
            record_history('discharge_followup',row,'contact_attempt',outcome=outcome)
        elif action=='complete':
            if g.membership.role!='dr':abort(403)
            if not row.planning_complete or row.status!='contacted':abort(400)
            outcome=request.form.get('outcome')
            if outcome not in ('followup_completed','care_team_reviewed','patient_declined','agreed_outcome_recorded'):abort(400)
            row.outcome=outcome;row.closure_reason=text('closure_reason',1000);row.status='completed'
        elif action=='escalate':
            row.escalated=True;record_history('discharge_followup',row,'escalated')
        elif action=='cancel':
            if g.membership.role!='dr':abort(403)
            row.closure_reason=text('closure_reason',1000);row.status='cancelled'
        else:abort(400)
        if action!='contact_attempt':record_history('discharge_followup',row,action)
        db.session.commit()
        return redirect(url_for('med.discharge_followup',admission_id=admission.id))
    if row:audit_views('discharge_followup',[row])
    return render_template('medical/coordination/discharge.html',patient=patient,admission=admission,
        row=row,team=staff_team(patient,True,'discharge'),history=history('discharge_followup',row.id) if row else [],
        policy=latest_policy('discharge'))


@bp.route('/med/referrals',methods=['GET','POST'])
@require_roles(*STAFF)
def referrals():
    if request.method=='POST':
        no_files();patient=lock_patient(request.form.get('patient_id',type=int),'referral')
        direction=request.form.get('direction');key=text('submission_key',64)
        if direction not in ('incoming','outgoing') or not all(c in '0123456789abcdef' for c in key) or len(key)<16:abort(400)
        other=text('other_party',200);requested=text('requested_action')
        prior=db.session.scalar(source_scope(Referral).where(Referral.institution_id==patient.institution_id,
            Referral.patient_id==patient.id,Referral.submission_key==key))
        if prior:
            if (prior.direction,prior.other_party,prior.requested_action)!=(direction,other,requested):abort(409)
            return redirect(url_for('med.referral_detail',referral_id=prior.id))
        owner=request.form.get('owner_id',type=int);validate_owner(patient,owner,kind='referral')
        if g.membership.role=='nurse' and owner!=current_user.id:abort(403)
        row=Referral(institution_id=patient.institution_id,patient_id=patient.id,direction=direction,
            other_party=other,requested_action=requested,referred_at=date('referred_at',True),
            owner_id=owner,due_at=date('due_at'),submission_key=key)
        if row.referred_at>utcnow():abort(400)
        practitioner_id=request.form.get('practitioner_id',type=int)
        if practitioner_id:
            if not can_patient(patient.id,'external_practitioners'):abort(403)
            practitioner=db.session.scalar(select(ExternalPractitioner).where(
                ExternalPractitioner.id==practitioner_id,ExternalPractitioner.patient_id==patient.id,
                ExternalPractitioner.institution_id==patient.institution_id))
            if not practitioner:abort(400)
            row.practitioner_id=practitioner.id
        db.session.add(row);db.session.flush();record_history('referral',row,'draft_created')
        db.session.commit();return redirect(url_for('med.referral_detail',referral_id=row.id))
    rows=list(db.session.scalars(source_scope(Referral).order_by(Referral.updated_at.desc())))
    audit_views('referral',rows)
    patients=list(db.session.scalars(coordination_patient_scope('referral').order_by(Patient.name)))
    teams={user.id:user for patient in patients for user in staff_team(patient,kind='referral')}
    return render_template('medical/coordination/referrals.html',referrals=rows,patients=patients,
        key=secrets.token_hex(16),teams=teams.values())


@bp.route('/med/referrals/<int:referral_id>',methods=['GET','POST'])
@require_roles(*STAFF)
def referral_detail(referral_id):
    row=source_row(Referral,referral_id);patient=coordination_patient(row.patient_id,'referral')
    if request.method=='POST':
        no_files();lock_patient(patient.id,'referral');row=source_row(Referral,referral_id,True)
        touch(row,request.form.get('version',type=int));action=request.form.get('action')
        if row.status in ('completed','declined','cancelled'):abort(409)
        if action=='assign':
            if g.membership.role not in ('dr','admin','dr_assist'):abort(403)
            operational_change(row,'referral',patient)
        elif action=='clinical_note':
            if g.membership.role!='dr':abort(403)
            note=ReferralClinical(referral_id=row.id,author_id=current_user.id,content=text('clinical_content',12000))
            db.session.add(note);db.session.flush();audit('author_referral_clinical','referral_clinical',note.id)
        elif action=='escalate':row.escalated=True
        elif action=='update':
            row.next_action=text('next_action',1000,False)
            row.outstanding_information=text('outstanding_information',1000,False)
            if g.membership.role=='dr':row.patient_visible=request.form.get('patient_visible')=='on'
        elif action=='transition':
            target=request.form.get('status')
            allowed=set(REFERRAL_TRANSITIONS[row.status])
            if row.status=='draft' and row.direction=='incoming':allowed.add('acknowledged')
            if target not in allowed:abort(400)
            if g.membership.role=='nurse':abort(403)  # record contacts/escalate, not clinical referral decisions
            if row.direction=='incoming' and target in ('accepted','declined') and g.membership.role!='dr':abort(403)
            if target=='sent':
                channel=request.form.get('consent_channel')
                decision=latest_decision(patient.id,'referral_sharing',channel,row.other_party)
                if not communication_allowed(patient.id,'referral_sharing',channel,row.other_party,False):abort(400)
                row.consent_id=decision.id
            if target in ('acknowledged','accepted','declined'):
                row.response_at=date('response_at',True)
                if row.response_at>utcnow() or row.response_at<row.referred_at:abort(400)
            if target=='appointment_arranged':
                identity=request.form.get('appointment_id',type=int)
                if identity:
                    appointment=db.session.scalar(select(Appointment).where(Appointment.id==identity,
                        Appointment.patient_id==patient.id,appointment_institution(patient.institution_id),
                        appointment_assignment(), Appointment.status=='scheduled'))
                    if not appointment:abort(400)
                    row.appointment_id=appointment.id;row.appointment_at=appointment.starts_at
                else:row.appointment_at=date('appointment_at',True)
            if target=='completed':
                if g.membership.role!='dr':abort(403)
                row.completed_at=date('completed_at',True)
                if row.completed_at>utcnow() or not row.appointment_at or row.completed_at<row.referred_at or row.completed_at<row.appointment_at:abort(400)
                row.closure_reason=text('closure_reason',1000)
            if target in ('cancelled','declined'):row.closure_reason=text('closure_reason',1000)
            row.status=target
        elif action=='reschedule':
            if g.membership.role=='nurse' or row.status!='appointment_arranged':abort(403)
            appointment=db.session.scalar(select(Appointment).where(
                Appointment.id==request.form.get('appointment_id',type=int),
                Appointment.patient_id==patient.id,appointment_institution(patient.institution_id),
                appointment_assignment(), Appointment.status=='scheduled'))
            if not appointment:abort(400)
            prior=row.appointment_id;row.appointment_id=appointment.id;row.appointment_at=appointment.starts_at
            record_history('referral',row,'appointment_rearranged',outcome=f'{prior or 0}->{appointment.id}')
        elif action=='contact_attempt':
            code=request.form.get('contact_outcome')
            if code not in ('no_answer','neutral_message','reached'):abort(400)
            record_history('referral',row,'contact_attempt',outcome=code)
        else:abort(400)
        if action!='contact_attempt':record_history('referral',row,action)
        db.session.commit()
        return redirect(url_for('med.referral_detail',referral_id=row.id))
    clinical=[]
    if can_patient(patient.id,'clinical_notes') or g.membership.role=='dr':
        clinical=list(db.session.scalars(select(ReferralClinical).where(ReferralClinical.referral_id==row.id)
            .order_by(ReferralClinical.id)))
        audit_views('referral_clinical',clinical)
    audit_views('referral',[row])
    return render_template('medical/coordination/referral.html',row=row,patient=patient,
        team=staff_team(patient,kind='referral'),history=history('referral',row.id),clinical=clinical,
        transitions=sorted(REFERRAL_TRANSITIONS[row.status] | ({'acknowledged'} if row.status=='draft' and row.direction=='incoming' else set())))


@bp.route('/med/coordination/consent',methods=['GET','POST'])
@require_roles(*STAFF,'patient')
def coordination_consent():
    if request.method=='POST':
        no_files();patient=lock_patient(request.form.get('patient_id',type=int))
        purpose=request.form.get('purpose');channel=request.form.get('channel');status=request.form.get('status')
        if purpose not in PURPOSES or channel not in CHANNELS or status not in ('granted','declined','withdrawn'):abort(400)
        if g.membership.role=='nurse':
            owns_discharge=db.session.scalar(select(DischargeFollowup.id).where(
                DischargeFollowup.patient_id==patient.id,DischargeFollowup.institution_id==patient.institution_id,
                (DischargeFollowup.owner_id==current_user.id)|(DischargeFollowup.cover_id==current_user.id)))
            owns_referral=db.session.scalar(source_scope(Referral).with_only_columns(Referral.id).where(Referral.patient_id==patient.id))
            if not (owns_discharge or owns_referral):abort(403)
        zone=text('timezone',80);scope=text('scope',200)
        try:ZoneInfo(zone)
        except (ValueError,ZoneInfoNotFoundError):abort(400)
        start=request.form.get('contact_start','');end=request.form.get('contact_end','')
        try:
            start=datetime.strptime(start,'%H:%M').time() if start else None
            end=datetime.strptime(end,'%H:%M').time() if end else None
        except ValueError:abort(400)
        if bool(start)!=bool(end):abort(400)
        destination=text('destination',254,False)
        if status=='granted' and (not destination or scope=='*'):abort(400)
        verified=request.form.get('verified')=='on' and g.membership.role!='patient'
        if channel=='portal':
            if not patient.user_id and status=='granted':abort(400)
            destination=str(patient.user_id) if patient.user_id else ''
            if g.membership.role=='patient':verified=True
        row=CommunicationDecision(institution_id=patient.institution_id,patient_id=patient.id,
            purpose=purpose,channel=channel,scope=scope,status=status,destination=destination,
            verified_at=utcnow() if verified else None,verified_by_id=current_user.id if verified else None,
            contact_start=start,contact_end=end,timezone=zone,method=text('method',80),
            notice_version=text('notice_version',120),recorded_by_id=current_user.id)
        db.session.add(row);db.session.flush();audit('record_consent_decision','communication_decision',row.id)
        if status!='granted' or not verified:
            suppress_unsent(patient,purpose,channel,scope,reason='consent_'+status if status!='granted' else 'destination_unverified')
        # Recheck queued records against all current purpose/channel/scope decisions.
        recheck_queued(patient)
        db.session.commit();return redirect(url_for('med.coordination_consent'))
    patients=list(db.session.scalars(patient_scope().order_by(Patient.name)))
    if g.membership.role=='nurse':
        allowed=set(db.session.scalars(select(DischargeFollowup.patient_id).where(
            DischargeFollowup.institution_id==g.membership.institution_id,
            (DischargeFollowup.owner_id==current_user.id)|(DischargeFollowup.cover_id==current_user.id))))
        allowed.update(db.session.scalars(source_scope(Referral).with_only_columns(Referral.patient_id)))
        patients=[p for p in patients if p.id in allowed]
    rows=list(db.session.scalars(select(CommunicationDecision).where(
        CommunicationDecision.institution_id==g.membership.institution_id,
        CommunicationDecision.patient_id.in_([p.id for p in patients])).order_by(CommunicationDecision.id.desc())))
    audit_views('communication_decision',rows)
    return render_template('medical/coordination/consent.html',patients=patients,decisions=rows,purposes=PURPOSES,channels=CHANNELS)


@bp.post('/med/coordination/recheck-notifications')
@require_roles('dr','admin','dr_assist')
def recheck_notifications():
    no_files();patient=lock_patient(request.form.get('patient_id',type=int));recheck_queued(patient)
    db.session.commit();return redirect(url_for('med.coordination_consent'))


@bp.route('/med/care-plans/<int:plan_id>/review',methods=['GET','POST'])
@require_roles('dr','nurse','admin')
def review_plan(plan_id):
    plan_meta=db.session.execute(select(CarePlan.id,CarePlan.patient_id,CarePlan.institution_id,CarePlan.author_id,
        CarePlan.review_at).where(CarePlan.id==plan_id,CarePlan.institution_id==g.membership.institution_id,
            CarePlan.patient_id.in_(coordination_patient_scope('review').with_only_columns(Patient.id)))).first()
    if not plan_meta:abort(404)
    patient=coordination_patient(plan_meta.patient_id,'review')
    rows=list(db.session.scalars(select(CareReview).where(CareReview.plan_id==plan_id,
        CareReview.institution_id==g.membership.institution_id).order_by(CareReview.sequence.desc())))
    pending=next((r for r in rows if r.status=='pending'),None)
    if g.membership.role=='nurse' and (not pending or current_user.id not in (pending.owner_id,pending.cover_id) or not can_patient(patient.id,'care_plan')):abort(404)
    if request.method=='POST':
        no_files();lock_patient(patient.id,'review')
        # Historical versions cannot be reactivated after a newer plan was agreed.
        latest_id=db.session.scalar(select(func.max(CarePlan.id)).where(CarePlan.patient_id==patient.id,
            CarePlan.institution_id==patient.institution_id))
        if latest_id!=plan_id:abort(409)
        pending=ensure_review(plan_meta)
        pending=db.session.scalar(select(CareReview).where(CareReview.id==pending.id).with_for_update().execution_options(populate_existing=True))
        if g.membership.role=='nurse' and (current_user.id not in (pending.owner_id,pending.cover_id) or not can_patient(patient.id,'care_plan')):abort(404)
        touch(pending,request.form.get('version',type=int))
        action=request.form.get('action')
        if action=='assign':
            if g.membership.role not in ('dr','admin'):abort(403)
            operational_change(pending,'care_review',patient,True,True)
            interval=request.form.get('interval_days',type=int)
            if interval is not None and not 1<=interval<=3650:abort(400)
            if g.membership.role!='dr' and interval is not None:abort(403)
            if interval is not None:
                pending.interval_days=interval
                if pending.due_at is None:pending.due_at=utcnow()+timedelta(days=interval)
        elif action=='escalate':pending.escalated=True
        elif action=='complete':
            if g.membership.role!='dr' or not pending.owner_id or not pending.due_at:abort(403)
            expected=request.form.get('review_id',type=int)
            if expected!=pending.id:abort(409)
            reviewed=date('reviewed_at',True);next_date=date('next_review_at',True)
            if reviewed>utcnow() or next_date<=utcnow() or next_date<=reviewed:abort(400)
            pending.reviewed_at=reviewed;pending.reviewer_id=current_user.id
            pending.next_review_at=next_date;pending.status='completed'
            from continuity_services import archive_events
            archive_events(patient,('overdue_followup',),'Clinician recorded an actual care-plan review.')
            db.session.add(CareReviewSignoff(review_id=pending.id,outcome=text('outcome',12000),
                reviewer_id=current_user.id,reviewed_at=reviewed))
            db.session.flush()  # release unique pending slot before scheduling the next review
            nxt=CareReview(institution_id=patient.institution_id,patient_id=patient.id,plan_id=plan_id,
                sequence=pending.sequence+1,owner_id=pending.owner_id,cover_id=pending.cover_id,
                due_at=next_date,interval_days=pending.interval_days)
            db.session.add(nxt);db.session.flush();record_history('care_review',nxt,'next_review_scheduled')
        else:abort(400)
        record_history('care_review',pending,action);db.session.commit()
        return redirect(url_for('med.review_plan',plan_id=plan_id))
    private=[]
    if can_patient(patient.id,'clinical_notes') or g.membership.role=='dr':
        private=list(db.session.scalars(select(CareReviewSignoff).where(
            CareReviewSignoff.review_id.in_([r.id for r in rows]))))
        audit_views('care_review_signoff',private)
    audit_views('care_review',rows)
    is_current=db.session.scalar(select(func.max(CarePlan.id)).where(CarePlan.patient_id==patient.id,
        CarePlan.institution_id==patient.institution_id))==plan_id
    goals=None
    if g.membership.role=='dr' or can_patient(patient.id,'care_plan'):
        goals=db.session.execute(select(CarePlan.goals,CarePlan.response_steps).where(
            CarePlan.id==plan_id,CarePlan.institution_id==g.membership.institution_id,CarePlan.patient_id==patient.id)).first()
    return render_template('medical/coordination/review.html',plan=plan_meta,patient=patient,
        rows=rows,pending=pending,signoffs=private,team=staff_team(patient,True,'review'),goals=goals,is_current=is_current)


@bp.route('/med/patients/<int:patient_id>/coordination-cover',methods=['GET','POST'])
@require_roles('dr')
def coordination_cover(patient_id):
    # General patient scope deliberately excludes delegated coverage: covers cannot delegate it again.
    patient=accessible_patient(patient_id)
    if request.method=='POST':
        no_files();lock_patient(patient.id)
        identity=request.form.get('user_id',type=int);kind=request.form.get('kind');status=request.form.get('status')
        if kind not in ('discharge','referral','review') or status not in ('granted','withdrawn') or identity==current_user.id:abort(400)
        target=db.session.scalar(select(Membership.id).join(User,User.id==Membership.user_id).where(
            Membership.institution_id==patient.institution_id,Membership.user_id==identity,
            Membership.role=='dr',Membership.enabled.is_(True),User.enabled.is_(True)))
        if not target:abort(400)
        end=date('valid_until',status=='granted')
        if status=='granted' and end<=utcnow():abort(400)
        row=CoordinationCoverage(institution_id=patient.institution_id,patient_id=patient.id,
            user_id=identity,kind=kind,status=status,valid_until=end,approved_by_id=current_user.id)
        db.session.add(row);db.session.flush();audit('record_coordination_cover','coordination_coverage',row.id)
        db.session.commit();return redirect(url_for('med.coordination_cover',patient_id=patient.id))
    candidates=list(db.session.execute(select(User.id,User.name).join(Membership,Membership.user_id==User.id).where(
        Membership.institution_id==patient.institution_id,Membership.role=='dr',Membership.enabled.is_(True),
        User.enabled.is_(True),User.id!=current_user.id)))
    rows=list(db.session.scalars(select(CoordinationCoverage).where(CoordinationCoverage.patient_id==patient.id,
        CoordinationCoverage.institution_id==patient.institution_id).order_by(CoordinationCoverage.id.desc())))
    audit_views('coordination_coverage',rows)
    return render_template('medical/coordination/cover.html',patient=patient,candidates=candidates,rows=rows)


def filtered_items():
    inst=request.args.get('institution',type=int)
    if request.args.get('institution') and inst is None:abort(400)
    if inst is not None and inst!=g.membership.institution_id:abort(403)
    rows=action_items()
    kind=request.args.get('type','');owner=request.args.get('owner','');status=request.args.get('status','active')
    due=request.args.get('due','');attention=request.args.get('attention','')
    if status not in ('active','all','open','contacted','pending','draft','sent','acknowledged','accepted',
        'appointment_arranged','completed','declined','cancelled','superseded','closed','archived','resolved','obsolete','dismissed','escalated'):abort(400)
    if kind and kind not in ('discharge','referral','review','continuity'):abort(400)
    if due not in ('','overdue','soon','missing'):abort(400)
    start=request.args.get('from','');end=request.args.get('to','')
    try:
        start=datetime.fromisoformat(start).date() if start else None
        end=datetime.fromisoformat(end).date() if end else None
    except ValueError:abort(400)
    if start and end and start>end:abort(400)
    if owner and owner not in ('me','unassigned'):
        try:int(owner)
        except ValueError:abort(400)
    selected=[]
    terminal=('completed','closed','cancelled','declined','archived','superseded','resolved','obsolete','dismissed')
    for row in rows:
        if kind and row['type']!=kind:continue
        if status=='active' and row['status'] in terminal:continue
        if status not in ('active','all') and row['status']!=status:continue
        if owner=='me' and row['owner_id']!=current_user.id:continue
        if owner=='unassigned' and row['owner_id'] is not None:continue
        if owner not in ('','me','unassigned') and row['owner_id']!=int(owner):continue
        if attention and attention not in row['reasons']:continue
        if due=='overdue' and (not row['due_at'] or row['due_at']>=utcnow()):continue
        if due=='soon' and 'Due soon' not in row['reasons']:continue
        if due=='missing' and row['due_at'] is not None:continue
        local=row['due_at'].replace(tzinfo=__import__('datetime').timezone.utc).astimezone(ZoneInfo('Africa/Johannesburg')).date() if row['due_at'] else None
        if start and (local is None or local<start):continue
        if end and (local is None or local>end):continue
        selected.append(row)
    return sorted(selected,key=lambda r:(r['due_at'] is not None,r['due_at'] or datetime.min,r['key']))


@bp.get('/med/actions')
@require_roles(*STAFF)
def my_actions():
    rows=filtered_items()
    cards={label:sum(label in r['reasons'] for r in rows) for label in
        ('Overdue','Due soon','Unassigned','Missing due date','Owner unavailable','Planning incomplete')}
    for row in rows:audit('view_sensitive','action_'+row['source'],int(row['source_id']) if str(row['source_id']).isdigit() else int(str(row['source_id']).split('-')[-1]))
    db.session.commit()
    filters=dict(request.args)
    return render_template('medical/coordination/actions.html',items=rows,cards=cards,filters=filters)


@bp.get('/med/my-agreed-actions')
@require_roles('patient')
def my_agreed_actions():
    rows=filtered_items()
    for row in rows:audit('view_sensitive','patient_agreed_action',row['patient_id'])
    db.session.commit()
    return render_template('medical/coordination/my_actions.html',items=rows)


@bp.post('/med/actions/export')
@require_roles('dr','admin')
def export_actions():
    no_files();rows=filtered_items()
    allowed=set(db.session.scalars(patient_scope('export').with_only_columns(Patient.id)))
    # The export is operational metadata only; it never includes clinical notes or referral content.
    rows=[r for r in rows if r['patient_id'] in allowed]
    if not rows:abort(404)
    from .permissions import csv_cell
    buffer=io.StringIO(newline='');writer=csv.writer(buffer)
    writer.writerow(['source','record_id','patient_id','owner_id','due_utc','status','attention','escalated'])
    for row in rows:
        writer.writerow([csv_cell(row[k]) for k in ('source','source_id','patient_id','owner_id','due_at','status','attention','escalated')])
        audit('export_action_metadata','patient',row['patient_id'])
    db.session.commit()
    return Response(buffer.getvalue(),mimetype='text/csv',headers={
        'Content-Disposition':'attachment; filename="authorized-actions.csv"','Cache-Control':'no-store'})


@bp.route('/med/actions/scheduling/<int:followup_id>',methods=['GET','POST'])
@require_roles(*STAFF)
def legacy_followup(followup_id):
    table=legacy_table('attendance_followups')
    if table is None:abort(404)
    query=select(table, Appointment.patient_id).join(Appointment,Appointment.id==table.c.appointment_id).where(table.c.id==followup_id,
        table.c.institution_id==g.membership.institution_id,
        appointment_institution(g.membership.institution_id), appointment_assignment(),
        Appointment.patient_id.in_(patient_scope().with_only_columns(Patient.id)))
    row=db.session.execute(query.with_for_update() if request.method=='POST' else query).mappings().first()
    if not row:abort(404)
    if g.membership.role=='nurse' and current_user.id not in (row.get('owner_id'),row.get('cover_id')):abort(404)
    patient=accessible_patient(row['patient_id'])
    if request.method=='POST':
        no_files()
        if request.form.get('version',type=int)!=row['revision']:abort(409)
        action=request.form.get('action','status');target=request.form.get('status')
        if row['state'] not in ('open','acknowledged'):abort(400)
        values=dict(revision=row['revision']+1,checked_at=utcnow())
        if action=='assign':
            if g.membership.role=='nurse':abort(403)
            if not all(c in table.c for c in ('owner_id','cover_id','due_at','escalated')):abort(409)
            owner=request.form.get('owner_id',type=int);cover=request.form.get('cover_id',type=int)
            validate_owner(patient,owner);validate_owner(patient,cover)
            values.update(owner_id=owner,cover_id=cover,due_at=date('due_at'),escalated=request.form.get('escalated')=='on')
            from types import SimpleNamespace
            record_history('attendance_followup',SimpleNamespace(id=row['id'],owner_id=owner,cover_id=cover),
                'assignment_updated',row.get('owner_id'),previous_cover=row.get('cover_id'))
        else:
            if action!='status' or target not in ('acknowledged','resolved','dismissed'):abort(400)
            values['state']=target
        db.session.execute(update(table).where(table.c.id==row['id'],table.c.institution_id==g.membership.institution_id,
            table.c.revision==row['revision']).values(**values))
        reviews=legacy_table('attendance_followup_reviews')
        if reviews is not None and action=='status':
            db.session.execute(reviews.insert().values(institution_id=g.membership.institution_id,
                followup_id=row['id'],actor_id=current_user.id,action=target,created_at=utcnow()))
        audit('review_scheduling_followup','attendance_followup',row['id']);db.session.commit()
        return redirect(url_for('med.my_actions'))
    audit('view_sensitive','attendance_followup',row['id']);db.session.commit()
    return render_template('medical/coordination/legacy.html',row=row,patient=patient,team=staff_team(patient),
        can_assign=all(c in table.c for c in ('owner_id','cover_id','due_at','escalated')))
