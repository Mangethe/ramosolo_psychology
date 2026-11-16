"""Permission matrix, least-privilege clinical views and deliberate data exports."""
import csv
import io
from flask import abort, g, render_template, request, redirect, url_for, Response
from flask_login import current_user
from sqlalchemy import select, or_
from extensions import db
from access import (READ_PERMISSIONS, ROLE_MATRIX, DELEGABLE, accessible_patient, audit,
                    audit_views, can_patient, continuity_scope, patient_scope,
                    require_roles, require_capability)
from models import (Patient, Membership, User, CareAssignment, PatientPermission, CarePlan,
                    ClinicalRecord, NursingObservation, ExternalPractitioner, PatientPreference,
                    Appointment, ContinuityEvent)
from medical_services import utcnow
from .continuity import text_field
from . import bp

RECORD_KINDS = ('diagnoses', 'clinical_notes', 'psychotherapy_notes')
PATIENT_PLAN_FIELDS = ('id', 'goals', 'warning_signs', 'channels', 'communication_consent',
    'planned_appointments', 'review_at', 'response_steps', 'urgent_help', 'monitoring_hours')


@bp.get('/med/permissions')
@require_roles(*ROLE_MATRIX)
def permission_matrix():
    return render_template('medical/permission_matrix.html', matrix=ROLE_MATRIX)


@bp.get('/med/patients/<int:patient_id>/permissions')
@require_capability('grant_access')
def patient_permissions(patient_id):
    patient = accessible_patient(patient_id)
    members = list(db.session.scalars(select(Membership).join(User, User.id == Membership.user_id).where(
        Membership.institution_id == patient.institution_id, Membership.role.in_(DELEGABLE),
        Membership.enabled.is_(True), User.enabled.is_(True))))
    grants = list(db.session.scalars(select(PatientPermission).where(
        PatientPermission.patient_id == patient.id, PatientPermission.institution_id == patient.institution_id)))
    return render_template('medical/patient_permissions.html', patient=patient, members=members,
                           grants=grants, permissions=READ_PERMISSIONS, delegable=DELEGABLE)


@bp.post('/med/patients/<int:patient_id>/permissions')
@require_capability('grant_access')
def change_patient_permission(patient_id):
    patient = accessible_patient(patient_id)
    db.session.execute(select(Patient.id).where(Patient.id == patient.id,
        Patient.institution_id == g.membership.institution_id).with_for_update())
    member = db.session.scalar(select(Membership).join(User, User.id == Membership.user_id).where(
        Membership.id == request.form.get('membership_id', type=int),
        Membership.institution_id == patient.institution_id, Membership.enabled.is_(True), User.enabled.is_(True)))
    permission = request.form.get('permission')
    action = request.form.get('action')
    if not member or permission not in DELEGABLE.get(member.role, set()) or action not in ('grant', 'revoke'):
        abort(400)
    if member.role == 'nurse' and not db.session.scalar(select(CareAssignment.id).where(
            CareAssignment.patient_id == patient.id, CareAssignment.nurse_id == member.user_id)):
        abort(400)
    grant = db.session.scalar(select(PatientPermission).where(
        PatientPermission.patient_id == patient.id, PatientPermission.institution_id == patient.institution_id,
        PatientPermission.membership_id == member.id, PatientPermission.permission == permission))
    if not grant:
        grant = PatientPermission(institution_id=patient.institution_id, patient_id=patient.id,
            membership_id=member.id, permission=permission, approved_by_id=current_user.id)
        db.session.add(grant)
    grant.enabled = action == 'grant'
    grant.approved_by_id = current_user.id
    grant.created_at = utcnow()
    db.session.flush()
    audit('grant_permission' if grant.enabled else 'revoke_permission', 'patient_permission', grant.id)
    db.session.commit()
    return redirect(url_for('med.patient_permissions', patient_id=patient.id))


def records_query(kind):
    return select(ClinicalRecord).where(ClinicalRecord.institution_id == g.membership.institution_id,
        ClinicalRecord.kind == kind,
        ClinicalRecord.patient_id.in_(patient_scope(kind).with_only_columns(Patient.id)))


@bp.get('/med/patients/<int:patient_id>/records/<kind>')
@require_capability('clinical_read')
def clinical_records(patient_id, kind):
    if kind not in RECORD_KINDS:
        abort(404)
    patient = accessible_patient(patient_id, kind)
    rows = list(db.session.scalars(records_query(kind).where(ClinicalRecord.patient_id == patient.id)
                                  .order_by(ClinicalRecord.id.desc())))
    audit_views('clinical_record', rows)
    return render_template('medical/records.html', patient=patient, rows=rows, kind=kind,
                           author= g.membership.role == 'dr')


@bp.post('/med/patients/<int:patient_id>/records/<kind>')
@require_capability('clinical_author')
def create_clinical_record(patient_id, kind):
    if kind not in RECORD_KINDS:
        abort(404)
    patient = accessible_patient(patient_id, kind)
    if request.form.get('clinician_confirmed') != 'on':
        abort(400)
    row = ClinicalRecord(institution_id=patient.institution_id, patient_id=patient.id,
        author_id=current_user.id, kind=kind, content=text_field('content', 12000))
    db.session.add(row); db.session.flush()
    audit('author_clinical_record', 'clinical_record', row.id)
    db.session.commit()
    return redirect(url_for('med.clinical_records', patient_id=patient.id, kind=kind))


@bp.get('/med/patients/<int:patient_id>/observations')
@require_capability('clinical_read')
def observations(patient_id):
    patient = accessible_patient(patient_id)
    query = select(NursingObservation).where(NursingObservation.patient_id == patient.id,
        NursingObservation.institution_id == patient.institution_id)
    if not can_patient(patient.id, 'observations'):
        if g.membership.role != 'nurse':
            abort(404)
        query = query.where(NursingObservation.author_id == current_user.id)
    rows = list(db.session.scalars(query.order_by(NursingObservation.id.desc())))
    audit_views('nursing_observation', rows)
    return render_template('medical/records.html', patient=patient, rows=rows, kind='observations',
                           author=g.membership.role == 'nurse')


@bp.post('/med/patients/<int:patient_id>/observations')
@require_capability('observe')
def create_observation(patient_id):
    patient = accessible_patient(patient_id)
    row = NursingObservation(institution_id=patient.institution_id, patient_id=patient.id,
        author_id=current_user.id, content=text_field('content', 4000),
        concern_escalated=request.form.get('escalate') == 'on')
    db.session.add(row); db.session.flush()
    audit('escalate_observation' if row.concern_escalated else 'record_observation', 'nursing_observation', row.id)
    db.session.commit()
    return redirect(url_for('med.observations', patient_id=patient.id))


@bp.get('/med/patients/<int:patient_id>/practitioners')
@require_capability('clinical_read')
def external_practitioners(patient_id):
    patient = accessible_patient(patient_id, 'external_practitioners')
    rows = list(db.session.scalars(select(ExternalPractitioner).where(
        ExternalPractitioner.patient_id == patient.id, ExternalPractitioner.institution_id == patient.institution_id)))
    audit_views('external_practitioner', rows)
    return render_template('medical/practitioners.html', patient=patient, practitioners=rows)


@bp.post('/med/patients/<int:patient_id>/practitioners')
@require_capability('clinical_author')
def reference_practitioner(patient_id):
    patient = accessible_patient(patient_id, 'external_practitioners')
    name = text_field('name', 120)
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    reference = request.form.get('registration_reference', '').strip()
    if len(email) > 254 or (email and '@' not in email) or len(phone) > 40 or len(reference) > 120:
        abort(400)
    row = ExternalPractitioner(institution_id=patient.institution_id, patient_id=patient.id,
        author_id=current_user.id, name=name, email=email, phone=phone, registration_reference=reference)
    db.session.add(row); db.session.flush()
    audit('reference_practitioner', 'external_practitioner', row.id)
    db.session.commit()
    return redirect(url_for('med.external_practitioners', patient_id=patient.id))


@bp.get('/med/my-care-plan')
@require_capability('patient_plan')
def my_care_plan():
    patients = list(db.session.scalars(patient_scope()))
    plans = []
    for patient in patients:
        # SQL projection: clinical definitions, internal rules and staff-only history are never fetched.
        row = db.session.execute(select(*(getattr(CarePlan, name) for name in PATIENT_PLAN_FIELDS),
            CarePlan.patient_visible).where(CarePlan.patient_id == patient.id,
            CarePlan.institution_id == g.membership.institution_id).order_by(CarePlan.id.desc()).limit(1)).mappings().first()
        from coordination_services import communication_allowed
        if row and row['patient_visible'] and communication_allowed(patient.id,'care_plan_sharing','portal',check_window=False):
            shared=dict(row)
            from models import CareReview
            signed_next=db.session.scalar(select(CareReview.next_review_at).where(
                CareReview.plan_id==row['id'],CareReview.patient_id==patient.id,
                CareReview.institution_id==g.membership.institution_id,CareReview.status=='completed')
                .order_by(CareReview.sequence.desc()).limit(1))
            if signed_next:shared['review_at']=signed_next
            plans.append(shared)
            audit('view_sensitive', 'patient_care_plan', row['id'])
    db.session.commit()
    return render_template('medical/my_care_plan.html', plans=plans, patients=patients)


@bp.route('/med/preferences', methods=['GET', 'POST'])
@require_capability('preferences')
def preferences():
    patients = list(db.session.scalars(patient_scope()))
    if request.method == 'POST':
        patient = accessible_patient(request.form.get('patient_id', type=int))
        channels = request.form.getlist('channels')
        consent = request.form.get('communication_consent')
        if consent not in ('yes', 'no') or any(c not in ('phone','email','sms','portal') for c in channels) or (consent == 'yes' and not channels):
            abort(400)
        row = db.session.scalar(select(PatientPreference).where(PatientPreference.patient_id == patient.id))
        if not row:
            row = PatientPreference(patient_id=patient.id)
            db.session.add(row)
        row.channels=channels; row.communication_consent=consent == 'yes'; row.updated_at=utcnow()
        # This legacy projection no longer grants purpose-specific consent. Declines restrict it.
        if consent=='no':
            from coordination_services import CHANNELS, suppress_unsent
            from models import CommunicationDecision
            for purpose in ('reminders','administrative_contact'):
                for channel in CHANNELS:
                    decision=CommunicationDecision(institution_id=patient.institution_id,patient_id=patient.id,
                        purpose=purpose,channel=channel,scope='*',status='withdrawn',destination='',
                        timezone='Africa/Johannesburg',method='patient_portal',notice_version='legacy-preferences-withdrawal-v1',
                        recorded_by_id=current_user.id)
                    db.session.add(decision)
                    db.session.flush();audit('record_consent_decision','communication_decision',decision.id)
                    suppress_unsent(patient,purpose,channel)
        db.session.flush(); audit('update_preferences', 'patient_preference', row.id)
        db.session.commit()
        return redirect(url_for('med.preferences'))
    rows = list(db.session.scalars(select(PatientPreference).where(
        PatientPreference.patient_id.in_([p.id for p in patients]))))
    audit_views('patient_preference', rows)
    return render_template('medical/preferences.html', patients=patients, preferences={r.patient_id:r for r in rows})


@bp.get('/med/charts/continuity')
@require_roles('dr','nurse','admin','dr_assist')
def continuity_chart():
    # Count and drill-down use the identical authorization query, including explicit grants.
    rows = list(db.session.scalars(continuity_scope().order_by(ContinuityEvent.id.desc())))
    audit_views('continuity_event', rows)
    totals = {category:sum(e.category == category for e in rows)
              for category in ('administrative','patient_reported','clinical')}
    return render_template('medical/continuity_chart.html', events=rows, totals=totals)


def csv_cell(value):
    value = '' if value is None else str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value


@bp.route('/med/exports', methods=['GET', 'POST'])
@require_capability('export')
def export_records():
    if request.method == 'GET':
        return render_template('medical/exports.html', resources=['operational', *sorted(READ_PERMISSIONS.keys() - {'export'})])
    resource = request.form.get('resource')
    if resource not in {'operational', *READ_PERMISSIONS.keys()} - {'export'}:
        abort(400)
    authorized = patient_scope('export').with_only_columns(Patient.id)
    readable = patient_scope(resource).where(Patient.id.in_(authorized))
    requested_id = request.form.get('patient_id', type=int)
    if request.form.get('patient_id', '').strip() and requested_id is None:
        abort(400)
    if requested_id is not None:
        if requested_id<=0:abort(400)
        readable = readable.where(Patient.id == requested_id)
    ids = list(db.session.scalars(readable.with_only_columns(Patient.id)))
    if not ids:
        abort(404)
    if resource == 'operational':
        rows = list(db.session.scalars(select(Patient).where(Patient.institution_id == g.membership.institution_id, Patient.id.in_(ids))))
        header = ['patient_id','name','email','phone']; data = [[r.id,r.name,r.email,r.phone] for r in rows]
        log_resource = 'patient'
    elif resource in RECORD_KINDS:
        rows = list(db.session.scalars(records_query(resource).where(ClinicalRecord.patient_id.in_(ids))))
        header = ['id','patient_id','kind','clinician_authored_content']; data = [[r.id,r.patient_id,r.kind,r.content] for r in rows]
        log_resource = 'clinical_record'
    elif resource in ('clinical_events','patient_concerns'):
        category = 'clinical' if resource == 'clinical_events' else 'patient_reported'
        rows = list(db.session.scalars(continuity_scope().where(ContinuityEvent.patient_id.in_(ids), ContinuityEvent.category == category)))
        header=['id','patient_id','category','kind','reason','state']; data=[[r.id,r.patient_id,r.category,r.kind,r.reason,r.state] for r in rows]
        log_resource='continuity_event'
    elif resource == 'care_plan':
        rows=list(db.session.execute(select(CarePlan.id, CarePlan.patient_id, CarePlan.goals, CarePlan.warning_signs,
            CarePlan.planned_appointments, CarePlan.review_at, CarePlan.response_steps).where(
                CarePlan.institution_id == g.membership.institution_id, CarePlan.patient_id.in_(ids))))
        # Exporting care information alone does not permit access to internal clinical definitions.
        header=['id','patient_id','agreed_goals','warning_signs','planned_appointments','review_at','agreed_response_steps']
        data=[[r.id,r.patient_id,r.goals,r.warning_signs,r.planned_appointments,r.review_at,r.response_steps] for r in rows]
        log_resource='care_plan'
    elif resource == 'observations':
        rows=list(db.session.scalars(select(NursingObservation).where(NursingObservation.institution_id == g.membership.institution_id, NursingObservation.patient_id.in_(ids))))
        header=['id','patient_id','observation','concern_escalated']; data=[[r.id,r.patient_id,r.content,r.concern_escalated] for r in rows]
        log_resource='nursing_observation'
    else:
        rows=list(db.session.scalars(select(ExternalPractitioner).where(ExternalPractitioner.institution_id == g.membership.institution_id, ExternalPractitioner.patient_id.in_(ids))))
        header=['id','patient_id','name','registration_reference','email','phone']; data=[[r.id,r.patient_id,r.name,r.registration_reference,r.email,r.phone] for r in rows]
        log_resource='external_practitioner'
    for row in rows:
        audit('export_sensitive' if resource != 'operational' else 'export_operational', log_resource, row.id)
    db.session.commit()
    output=io.StringIO(newline=''); writer=csv.writer(output); writer.writerow(header)
    writer.writerows([[csv_cell(v) for v in row] for row in data])
    return Response(output.getvalue(), mimetype='text/csv', headers={
        'Content-Disposition':'attachment; filename="authorized-records.csv"', 'Cache-Control':'no-store'})
