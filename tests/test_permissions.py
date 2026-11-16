import csv
import io
import pytest
from flask import g
from sqlalchemy import select, func
from extensions import db
from models import (Patient, Membership, PatientPermission, CareAssignment, ClinicalRecord,
                    NursingObservation, ExternalPractitioner, AuditEvent, User, ContinuityEvent,
                    PatientPreference, CarePlan)
from test_medical import env, as_user
from test_continuity import approve, plan_form, create_event, event, submit, consent


def grant(env, role, permission, action='grant', patient=None):
    patient = patient or env[2][0]
    member=db.session.scalar(select(Membership).where(Membership.user_id==env[1][role].id))
    return as_user(env,'dr').post(f'/med/patients/{patient.id}/permissions',data=dict(
        membership_id=member.id,permission=permission,action=action))


def write_record(env, kind='diagnoses', content='SYNTHETIC CLINICAL SECRET'):
    response=as_user(env,'dr').post(f'/med/patients/{env[2][0].id}/records/{kind}',data=dict(
        content=content,clinician_confirmed='on'))
    assert response.status_code==302
    return db.session.scalar(select(ClinicalRecord).order_by(ClinicalRecord.id.desc()))


@pytest.mark.parametrize('role',['dr','nurse','dr_assist','patient','admin'])
def test_every_role_matrix_and_default_clinical_isolation(env,role):
    p=env[2][0]
    # No automatic clinical permissions are issued by a care assignment or an account role.
    form=plan_form(env)
    as_user(env,'dr').post(f'/med/patients/{p.id}/care-plan',data=form)
    write_record(env);write_record(env,'clinical_notes');write_record(env,'psychotherapy_notes')
    create_event(env)
    e=event()
    client=as_user(env,role)
    assert client.get('/med/permissions').status_code==200
    for kind in ['diagnoses','clinical_notes','psychotherapy_notes']:
        r=client.get(f'/med/patients/{p.id}/records/{kind}')
        assert r.status_code==(200 if role=='dr' else 404 if role in ('nurse','admin') else 403)
        if role!='dr':assert b'SYNTHETIC CLINICAL SECRET' not in r.data
        assert client.post(f'/med/patients/{p.id}/records/{kind}',data=dict(
            content='FORGED',clinician_confirmed='on')).status_code==(302 if role=='dr' else 403)
    assert client.get(f'/med/continuity/{e.id}').status_code==(200 if role=='dr' else 403 if role=='patient' else 404)
    if role!='dr':
        assert b'Synthetic observed context' not in client.get('/med/charts/continuity').data
        assert client.post(f'/med/patients/{p.id}/permissions',data={}).status_code==403
    assert client.post('/med/exports',data={'resource':'diagnoses'}).status_code==(200 if role=='dr' else 404 if role=='admin' else 403)


@pytest.mark.parametrize('role',['dr','nurse','dr_assist','patient','admin'])
def test_every_role_cross_patient_and_institution_clinical_attempts(env,role):
    write_record(env)
    client=as_user(env,role)
    for patient in env[2][1:]:
        expected=403 if role in ('patient','dr_assist') else 404
        for suffix in ['care-plan','records/diagnoses','records/clinical_notes','records/psychotherapy_notes','practitioners']:
            assert client.get(f'/med/patients/{patient.id}/{suffix}').status_code==expected,(role,suffix)
        for suffix in ['care-plan','records/diagnoses','practitioners','permissions']:
            assert client.post(f'/med/patients/{patient.id}/{suffix}',data={}).status_code==(404 if role=='dr' else 403)
        assert client.post(f'/med/patients/{patient.id}/observations',data={'content':'Forged'}).status_code==(404 if role=='nurse' else 403)
        assert client.post('/med/exports',data={'resource':'diagnoses','patient_id':patient.id}).status_code==(404 if role in ('dr','admin') else 403)


def test_admin_grants_are_resource_specific_read_only_and_revocable(env):
    approve(env);write_record(env);write_record(env,'clinical_notes');create_event(env)
    p=env[2][0];e=event()
    assert grant(env,'admin','diagnoses').status_code==302
    client=as_user(env,'admin')
    assert b'SYNTHETIC CLINICAL SECRET' in client.get(f'/med/patients/{p.id}/records/diagnoses').data
    assert client.get(f'/med/patients/{p.id}/records/clinical_notes').status_code==404
    assert client.get(f'/med/continuity/{e.id}').status_code==404
    assert client.post(f'/med/patients/{p.id}/records/diagnoses',data=dict(content='FORGED',clinician_confirmed='on')).status_code==403
    assert client.post(f'/med/patients/{p.id}/permissions',data=dict(permission='psychotherapy_notes',action='grant')).status_code==403
    grant(env,'admin','clinical_events')
    client=as_user(env,'admin')
    assert client.get(f'/med/continuity/{e.id}').status_code==200
    assert client.post(f'/med/continuity/{e.id}',data=dict(action='close',detail='FORGED')).status_code==403
    grant(env,'admin','diagnoses','revoke')
    assert as_user(env,'admin').get(f'/med/patients/{p.id}/records/diagnoses').status_code==404


def test_grants_never_bypass_assignment_institution_or_current_authorizer(env):
    approve(env);write_record(env)
    assert grant(env,'foreign','diagnoses').status_code==400
    assert grant(env,'patient','diagnoses').status_code==400
    assert grant(env,'dr_assist','diagnoses').status_code==400
    assert grant(env,'nurse','psychotherapy_notes').status_code==400
    assert grant(env,'admin','diagnoses',patient=env[2][1]).status_code==404
    grant(env,'nurse','diagnoses');grant(env,'admin','diagnoses')
    p=env[2][0]
    assignment=db.session.scalar(select(CareAssignment).where(CareAssignment.patient_id==p.id))
    db.session.delete(assignment);db.session.commit()
    assert as_user(env,'nurse').get(f'/med/patients/{p.id}/records/diagnoses').status_code==404
    m=db.session.scalar(select(Membership).where(Membership.user_id==env[1]['dr'].id))
    m.enabled=False;db.session.commit()
    assert as_user(env,'admin').get(f'/med/patients/{p.id}/records/diagnoses').status_code==404
    m.enabled=True;p.doctor_id=env[1]['dr2'].id;db.session.commit()
    assert as_user(env,'admin').get(f'/med/patients/{p.id}/records/diagnoses').status_code==404


def test_nurse_observations_and_assigned_task_boundary(env):
    approve(env);create_event(env);e=event();p=env[2][0]
    write_record(env)
    client=as_user(env,'nurse')
    assert client.post(f'/med/patients/{p.id}/observations',data={'content':'OBSERVATION ONLY','escalate':'on'}).status_code==302
    row=db.session.scalar(select(NursingObservation))
    assert row.concern_escalated and row.author_id==env[1]['nurse'].id
    assert db.session.scalar(select(func.count(ClinicalRecord.id)))==1
    assert db.session.scalar(select(func.count(ContinuityEvent.id)))==1
    assert b'not diagnoses' in client.get(f'/med/patients/{p.id}/observations').data
    assert client.post(f'/med/continuity/{e.id}',data=dict(action='acknowledge',detail='Accepted assigned task')).status_code==302
    # Read grant is not sufficient to modify a task owned by somebody else.
    e.owner_id=env[1]['dr'].id;db.session.commit()
    assert client.get(f'/med/continuity/{e.id}').status_code==200
    assert client.post(f'/med/continuity/{e.id}',data=dict(action='close',detail='FORGED')).status_code==403
    assert client.post('/med/continuity/events',data=dict(patient_id=p.id,kind='relapse',reason='FORGED',definition_confirmed='on')).status_code==403
    assert b'OBSERVATION ONLY' in as_user(env,'dr').get(f'/med/patients/{p.id}/observations').data


def test_patient_published_projection_preferences_and_no_confirmation_authority(env):
    p=env[2][0];form=plan_form(env)
    form['clinical_definitions']='INTERNAL CLINICAL DEFINITION'
    client=as_user(env,'dr')
    client.post(f'/med/patients/{p.id}/care-plan',data=form)
    assert b'Agreed synthetic goal' not in as_user(env,'patient').get('/med/my-care-plan').data
    form['share_with_patient']='on'
    as_user(env,'dr').post(f'/med/patients/{p.id}/care-plan',data=form)
    consent(env,'care_plan_sharing','portal')
    write_record(env)
    client=as_user(env,'patient')
    body=client.get('/med/my-care-plan').data
    assert b'Agreed synthetic goal' in body and b'INTERNAL CLINICAL DEFINITION' not in body
    assert b'SYNTHETIC CLINICAL SECRET' not in body
    assert client.post('/med/preferences',data=dict(patient_id=p.id,communication_consent='no')).status_code==302
    assert not db.session.scalar(select(PatientPreference)).communication_consent
    assert client.post('/med/preferences',data=dict(patient_id=env[2][1].id,communication_consent='no')).status_code==404
    assert client.post('/med/check-in',data=dict(patient_id=p.id,kind='contact_request',reason='Patient-reported relapse wording',monitoring_understood='on')).status_code==302
    assert event().category=='patient_reported'
    assert db.session.scalar(select(func.count(ClinicalRecord.id)))==1
    assert as_user(env,'dr').post(f'/med/continuity/{event().id}',data=dict(action='sandbox_notification',channel='phone',detail='Preview')).status_code==400


def test_care_plan_grant_excludes_internal_clinical_definitions_and_related_event_plan(env):
    approve(env);create_event(env)
    p=env[2][0];e=event()
    grant(env,'admin','care_plan')
    client=as_user(env,'admin')
    response=client.get(f'/med/patients/{p.id}/care-plan')
    assert response.status_code==200 and b'Agreed synthetic goal' in response.data
    assert b'Synthetic practice definitions' not in response.data
    grant(env,'nurse','care_plan','revoke')
    response=as_user(env,'nurse').get(f'/med/continuity/{e.id}')
    assert response.status_code==200
    assert b'Contact using agreed channel' not in response.data


def test_export_requires_separate_authorization_and_scoped_csv_is_safe(env):
    write_record(env,content='=SYNTHETIC_FORMULA()')
    other=ClinicalRecord(institution_id=env[2][2].institution_id,patient_id=env[2][2].id,
        author_id=env[1]['foreign'].id,kind='diagnoses',content='FOREIGN SECRET')
    db.session.add(other);db.session.commit()
    grant(env,'admin','diagnoses')
    assert as_user(env,'admin').post('/med/exports',data={'resource':'diagnoses'}).status_code==404
    grant(env,'admin','export')
    client=as_user(env,'admin')
    response=client.post('/med/exports',data={'resource':'diagnoses'})
    assert response.status_code==200 and response.headers['Cache-Control']=='no-store'
    assert b'FOREIGN SECRET' not in response.data
    rows=list(csv.reader(io.StringIO(response.text)))
    assert len(rows)==2 and rows[1][-1].startswith("'=SYNTHETIC")
    assert client.post('/med/exports',data={'resource':'clinical_notes'}).status_code==404
    assert client.post('/med/exports',data={'resource':'diagnoses','patient_id':env[2][2].id}).status_code==404
    assert client.post('/med/exports',data={'resource':'diagnoses','patient_id':'invalid'}).status_code==400
    assert client.post('/med/exports',data={'resource':'unknown'}).status_code==400
    assert client.get('/med/exports?resource=diagnoses').mimetype=='text/html'


def test_external_psychiatrist_is_a_reference_without_account(env):
    p=env[2][0]
    before=db.session.scalar(select(func.count(User.id)))
    memberships=db.session.scalar(select(func.count(Membership.id)))
    client=as_user(env,'dr')
    assert client.post(f'/med/patients/{p.id}/practitioners',data=dict(name='Synthetic External Psychiatrist',email='reference@example.test',phone='000',registration_reference='SYNTHETIC')).status_code==302
    assert db.session.scalar(select(func.count(ExternalPractitioner.id)))==1
    assert db.session.scalar(select(func.count(User.id)))==before
    assert db.session.scalar(select(func.count(Membership.id)))==memberships
    for role in ['admin','nurse','dr_assist','patient']:
        response=as_user(env,role).get(f'/med/patients/{p.id}/practitioners')
        assert response.status_code==(404 if role in ('admin','nurse') else 403)
    grant(env,'admin','external_practitioners')
    assert b'Synthetic External Psychiatrist' in as_user(env,'admin').get(f'/med/patients/{p.id}/practitioners').data


def test_sensitive_views_changes_and_exports_audit_ids_without_content(env):
    row=write_record(env,content='SENSITIVE CONTENT NEVER LOGGED')
    client=as_user(env,'dr')
    client.get(f'/med/patients/{env[2][0].id}/records/diagnoses')
    client.post('/med/exports',data={'resource':'diagnoses'})
    logs=list(db.session.scalars(select(AuditEvent).where(AuditEvent.resource_type=='clinical_record',AuditEvent.resource_id==row.id)))
    assert {'author_clinical_record','view_sensitive','export_sensitive'} <= {e.action for e in logs}
    for log in db.session.scalars(select(AuditEvent)):
        assert log.institution_id==env[2][0].institution_id
        assert 'SENSITIVE CONTENT' not in str((log.action,log.resource_type,log.resource_id))


def test_chart_drilldowns_follow_grants_and_assistants_have_no_admissions(env):
    approve(env);create_event(env);e=event()
    grant(env,'admin','clinical_events')
    assert b'Synthetic observed context' in as_user(env,'admin').get(f'/med/continuity/{e.id}').data
    grant(env,'admin','clinical_events','revoke')
    client=as_user(env,'admin')
    assert f'/med/continuity/{e.id}'.encode() not in client.get('/med/charts/continuity').data
    assert client.get(f'/med/continuity/{e.id}').status_code==404
    client=as_user(env,'dr_assist')
    assert client.get('/med/admissions').status_code==403
    assert b'Test Facility' not in client.get(f'/med/patients/{env[2][0].id}').data


def test_csrf_new_modules_and_unknown_permissions_fail_closed(env):
    p=env[2][0];env[0].config['WTF_CSRF_ENABLED']=True
    client=as_user(env,'dr')
    for path in [f'/med/patients/{p.id}/permissions',f'/med/patients/{p.id}/records/diagnoses',
                 f'/med/patients/{p.id}/practitioners','/med/exports']:
        assert client.post(path,data={}).status_code==400
    assert as_user(env,'nurse').post(f'/med/patients/{p.id}/observations',data={}).status_code==400
    assert as_user(env,'patient').post('/med/preferences',data={}).status_code==400
    env[0].config['WTF_CSRF_ENABLED']=False
    assert grant(env,'admin','unknown').status_code==400
    assert as_user(env,'edu').get('/med/permissions').status_code==403
    g.pop('_login_user',None)
    assert env[0].test_client().get('/med/my-care-plan').status_code==302


def test_local_upgrade_does_not_grant_or_publish_and_sql_parameters_are_hidden(env):
    from sqlalchemy import text, inspect
    assert db.engine.hide_parameters and not db.engine.echo
    form=plan_form(env);form['share_with_patient']='on'
    as_user(env,'dr').post(f'/med/patients/{env[2][0].id}/care-plan',data=form)
    # Synthetic legacy schema, never a real database file.
    db.session.execute(text('ALTER TABLE care_plans DROP COLUMN patient_visible'))
    db.session.commit()
    result=env[0].test_cli_runner().invoke(args=['upgrade-permissions'])
    assert result.exit_code==0, result.output
    assert 'patient_visible' in {c['name'] for c in inspect(db.engine).get_columns('care_plans')}
    assert db.session.scalar(select(func.count(PatientPermission.id)))==0
    plan=db.session.scalar(select(CarePlan))
    assert plan.goals=='Agreed synthetic goal' and not plan.patient_visible
    assert env[0].test_cli_runner().invoke(args=['upgrade-permissions']).exit_code==0


def test_patient_plan_and_preferences_query_parameters_never_switch_patient(env):
    p=env[2][0];form=plan_form(env);form['share_with_patient']='on'
    as_user(env,'dr').post(f'/med/patients/{p.id}/care-plan',data=form)
    consent(env,'care_plan_sharing','portal')
    foreign=CarePlan(institution_id=env[2][2].institution_id,patient_id=env[2][2].id,
        author_id=env[1]['foreign'].id,owner_id=env[1]['foreign'].id,goals='FOREIGN PATIENT PLAN',
        warning_signs='Synthetic',channels=['portal'],communication_consent=True,
        planned_appointments='Synthetic',review_at=env[3][2].starts_at,response_steps='Synthetic',
        urgent_help='Synthetic',monitoring_hours='Synthetic',rules={},clinical_definitions='PRIVATE',
        patient_visible=True,agreed_at=env[3][2].starts_at)
    db.session.add(foreign);db.session.commit()
    client=as_user(env,'patient')
    assert b'FOREIGN PATIENT PLAN' not in client.get(f'/med/my-care-plan?patient_id={env[2][2].id}').data
    response=client.get(f'/med/preferences?patient_id={env[2][2].id}')
    assert f'name="patient_id" value="{p.id}"'.encode() in response.data
    assert f'name="patient_id" value="{env[2][2].id}"'.encode() not in response.data


def test_forged_stored_grants_fail_closed_and_exception_parameters_are_redacted(env):
    from sqlalchemy.exc import IntegrityError
    p=env[2][0];write_record(env)
    member=db.session.scalar(select(Membership).where(Membership.user_id==env[1]['admin'].id))
    row=PatientPermission(institution_id=p.institution_id,patient_id=p.id,membership_id=member.id,
        permission='diagnoses',approved_by_id=env[1]['admin'].id,enabled=True)
    db.session.add(row);db.session.commit()
    assert as_user(env,'admin').get(f'/med/patients/{p.id}/records/diagnoses').status_code==404
    row.approved_by_id=env[1]['dr'].id;row.institution_id=env[2][2].institution_id;db.session.commit()
    assert as_user(env,'admin').get(f'/med/patients/{p.id}/records/diagnoses').status_code==404
    invalid=ClinicalRecord(institution_id=p.institution_id,patient_id=999999,author_id=env[1]['dr'].id,
        kind='diagnoses',content='SYNTHETIC_VALUE_MUST_NOT_APPEAR_IN_SQL_ERRORS')
    db.session.add(invalid)
    with pytest.raises(IntegrityError) as failure:
        db.session.flush()
    assert invalid.content not in str(failure.value)
    db.session.rollback()
