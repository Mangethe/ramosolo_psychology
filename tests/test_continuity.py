from datetime import timedelta
import pytest
from flask import g
from sqlalchemy import select, func
from extensions import db
from models import (CarePlan, ContinuityEvent, ContinuityHistory, ContinuityNotification,
                    Appointment, CareAssignment)
from medical_services import utcnow, TZ
from continuity_services import KINDS
from test_medical import env, as_user


def local(value):
    from datetime import timezone
    return value.replace(tzinfo=timezone.utc).astimezone(TZ).isoformat(timespec='minutes')


def plan_form(env):
    return dict(owner_id=env[1]['nurse'].id, goals='Agreed synthetic goal',
        warning_signs='Individually agreed synthetic signs', channels=['phone', 'portal'],
        communication_consent='yes', planned_appointments='Agreed appointment next week',
        review_at=local(utcnow()+timedelta(days=14)), response_steps='Contact using agreed channel; clinician reviews next steps.',
        urgent_help='Synthetic practice-approved urgent-help instructions.',
        monitoring_hours='Synthetic schedule: Monday to Friday, 09:00â€“16:00 Africa/Johannesburg; closed on public holidays.',
        clinical_definitions='Synthetic practice definitions: clinician-documented assessment required.',
        patient_agreed='on', practice_approved='on', **{'rule_'+k:'120' for k in KINDS})


def approve(env):
    response=as_user(env,'dr').post(f'/med/patients/{env[2][0].id}/care-plan',data=plan_form(env))
    assert response.status_code==302
    # Nurses require separate, deliberate patient-specific grants; assignment alone is insufficient.
    from models import Membership
    member=db.session.scalar(select(Membership).where(Membership.user_id==env[1]['nurse'].id))
    for permission in ['care_plan','clinical_events','patient_concerns','observations','external_practitioners']:
        assert as_user(env,'dr').post(f'/med/patients/{env[2][0].id}/permissions',data=dict(
            membership_id=member.id,permission=permission,action='grant')).status_code==302
    consent(env)
    return db.session.scalar(select(CarePlan).order_by(CarePlan.id.desc()))


def consent(env,purpose='administrative_contact',channel='phone',scope='practice',status='granted'):
    # An explicit synthetic consent capture, not an implied opt-in from the plan or account.
    return as_user(env,'dr').post('/med/coordination/consent',data=dict(
        patient_id=env[2][0].id,purpose=purpose,channel=channel,scope=scope,status=status,
        destination='synthetic-verified-destination',verified='on',timezone='Africa/Johannesburg',
        method='synthetic-in-person',notice_version='synthetic-notice-v1'))


def create_event(env,kind='relapse',role='dr',**extra):
    return as_user(env,role).post('/med/continuity/events',data=dict(
        patient_id=env[2][0].id,kind=kind,reason='Synthetic observed context',
        definition_confirmed='on',**extra))


def event():
    return db.session.scalar(select(ContinuityEvent).order_by(ContinuityEvent.id.desc()))


def submit(env,kind='check_in',**extra):
    form=dict(patient_id=env[2][0].id,kind=kind,reason='Synthetic patient message',monitoring_understood='on')
    form.update(extra)
    return as_user(env,'patient').post('/med/check-in',data=form)


def test_plan_approval_versioning_and_pages(env):
    p=approve(env)
    assert p.author_id==env[1]['dr'].id and p.rules['relapse']==120
    assert p.communication_consent and p.agreed_at
    assert p.owner_id==env[1]['nurse'].id
    second=approve(env)
    assert second.id!=p.id and db.session.scalar(select(func.count(CarePlan.id)))==2
    for role in ['dr','nurse']:
        assert as_user(env,role).get(f'/med/patients/{env[2][0].id}/care-plan').status_code==200
        assert as_user(env,role).get('/med/continuity').status_code==200
    r=as_user(env,'patient').get('/med/check-in')
    assert b'09:00' in r.data and b'not continuously monitored' in r.data
    assert b'Agreed synthetic goal' not in r.data
    assert b'practice definitions' not in r.data


@pytest.mark.parametrize('role',['admin','dr_assist','nurse','patient'])
def test_only_assigned_doctor_authors_plans(env,role):
    assert as_user(env,role).post(f'/med/patients/{env[2][0].id}/care-plan',data=plan_form(env)).status_code==403
    if role!='nurse':
        assert as_user(env,role).get(f'/med/patients/{env[2][0].id}/care-plan').status_code==(404 if role=='admin' else 403)


def test_plan_scope_and_validation(env):
    client=as_user(env,'dr')
    assert client.post(f'/med/patients/{env[2][1].id}/care-plan',data=plan_form(env)).status_code==404
    for field,value in [('patient_agreed',''),('practice_approved',''),('monitoring_hours',''),
                        ('rule_relapse','0'),('rule_check_in','abc'),('owner_id',env[1]['foreign'].id),
                        ('owner_id',env[1]['dr2'].id),('communication_consent','unknown'),
                        ('channels',['carrier_pigeon']),('review_at',local(utcnow()-timedelta(days=1)))]:
        form=plan_form(env);form[field]=value
        assert client.post(f'/med/patients/{env[2][0].id}/care-plan',data=form).status_code==400,field
    assert db.session.scalar(select(func.count(CarePlan.id)))==0


def test_no_plan_no_inferred_rule_no_submission(env):
    assert b'unavailable' in as_user(env,'patient').get('/med/check-in').data
    assert submit(env).status_code==302
    create_event(env)
    assert event() is None
    form=plan_form(env)
    for kind in KINDS: form.pop('rule_'+kind)
    as_user(env,'dr').post(f'/med/patients/{env[2][0].id}/care-plan',data=form)
    create_event(env)
    assert event() is None
    assert b'not been enabled' in as_user(env,'patient').get('/med/check-in').data


def test_missed_appointment_only_administrative_deduplicated(env):
    approve(env)
    a=env[3][0];a.starts_at=utcnow()-timedelta(days=1);db.session.commit()
    client=as_user(env,'admin')
    for _ in range(2):
        assert client.post(f'/med/appointments/{a.id}/status',data={'status':'no_show'}).status_code==302
    e=event()
    assert e.category=='administrative' and e.kind=='missed_appointment' and not e.definition
    assert db.session.scalar(select(func.count(ContinuityEvent.id)))==1
    assert e.owner_id==env[1]['nurse'].id
    assert 119*60 < (e.due_at-e.created_at).total_seconds() <= 120*60
    assert a.status=='no_show'
    as_user(env,'admin').post(f'/med/continuity/{e.id}',data=dict(action='close',detail='Resolved administrative interruption'))
    as_user(env,'admin').post(f'/med/appointments/{a.id}/status',data={'status':'no_show'})
    assert e.state=='closed' and db.session.scalar(select(func.count(ContinuityEvent.id)))==1


def test_no_show_without_approved_rule_never_creates_clinical_event(env):
    a=env[3][0];a.starts_at=utcnow()-timedelta(days=1);db.session.commit()
    as_user(env,'dr').post(f'/med/appointments/{a.id}/status',data={'status':'no_show'})
    assert a.status=='no_show' and event() is None


@pytest.mark.parametrize('kind',['contact_request','check_in'])
def test_patient_submission_optional_dedup_keeps_messages_and_due(env,kind):
    approve(env)
    assert submit(env,kind).status_code==302
    e=event();due=e.due_at
    assert e.category=='patient_reported' and e.author_id==env[1]['patient'].id
    submit(env,kind,reason='Second synthetic submission')
    assert db.session.scalar(select(func.count(ContinuityEvent.id)))==1 and e.due_at==due
    assert db.session.scalar(select(ContinuityHistory).where(ContinuityHistory.action=='submission')).detail=='Second synthetic submission'
    assert as_user(env,'patient').get('/med/continuity').status_code==403
    assert as_user(env,'patient').get(f'/med/continuity/{e.id}').status_code==403
    assert b'not continuously monitored' in as_user(env,'patient').get('/med/check-in').data
    assert env[3][0].status=='scheduled'
    assert env[1]['patient'].enabled


def test_patient_cannot_forge_kind_or_other_patient_or_skip_notice(env):
    approve(env)
    assert submit(env,kind='relapse').status_code==400
    assert submit(env,patient_id=env[2][1].id).status_code==404
    assert submit(env,monitoring_understood='').status_code==400
    assert event() is None
    assert as_user(env,'dr').post('/med/check-in',data={}).status_code==403


def test_clinical_event_requires_doctor_and_definition_confirmation(env):
    approve(env)
    for role in ['admin','nurse','dr_assist']:
        assert create_event(env,role=role).status_code==403
    assert as_user(env,'dr').post('/med/continuity/events',data=dict(
        patient_id=env[2][0].id,kind='relapse',reason='synthetic')).status_code==400
    for kind in ['deterioration','lapse','relapse']:
        create_event(env,kind)
        e=event()
        assert e.category=='clinical' and e.kind==kind and e.definition.startswith('Synthetic practice definitions')
    assert env[3][0].status=='scheduled'
    e=event();due=e.due_at
    create_event(env,'relapse')
    assert db.session.scalar(select(func.count(ContinuityEvent.id)))==3
    assert e.due_at==due and e.history[-1].action=='clinical_update'


def test_queue_detail_and_mutations_scoped_by_assignment_and_role(env):
    approve(env);create_event(env)
    clinical=event()
    submit(env)
    concern=event()
    for role in ['admin','dr_assist','dr2','foreign']:
        for e in [clinical,concern]:
            client=as_user(env,role)
            assert client.get(f'/med/continuity/{e.id}').status_code==404
            assert client.post(f'/med/continuity/{e.id}',data=dict(action='close',detail='Forged')).status_code==404
        assert b'Synthetic observed context' not in as_user(env,role).get('/med/continuity').data
    for role in ['dr','nurse']:
        assert as_user(env,role).get(f'/med/continuity/{clinical.id}').status_code==200
    assignment=db.session.scalar(select(CareAssignment).where(CareAssignment.nurse_id==env[1]['nurse'].id))
    db.session.delete(assignment);db.session.commit()
    assert as_user(env,'nurse').get(f'/med/continuity/{clinical.id}').status_code==404
    assert submit(env).status_code==302
    # Unavailable owners prevent silent routing to an unassigned team member.
    assert db.session.scalar(select(func.count(ContinuityEvent.id)))==2


def test_followup_lifecycle_and_immutable_deadline(env):
    approve(env);create_event(env)
    e=event();due=e.due_at
    client=as_user(env,'nurse')
    for action,detail in [('acknowledge','Received'),('contact_attempt','Phone attempted; no answer'),
                          ('outcome','Patient requested later contact'),('escalate','Agreed clinician review'),
                          ('close','Resolved with patient')]:
        if action == 'close':
            client=as_user(env,'dr')  # escalation transferred the assigned task to the clinician
        assert client.post(f'/med/continuity/{e.id}',data=dict(action=action,detail=detail,
            owner_id=env[1]['dr'].id,due_at=local(utcnow()+timedelta(days=99)))).status_code==302
    assert e.state=='closed' and e.owner_id==env[1]['dr'].id and e.due_at==due
    assert [h.action for h in e.history]==['created','acknowledge','contact_attempt','outcome','escalate','close']
    assert client.post(f'/med/continuity/{e.id}',data=dict(action='outcome',detail='Rewrite closed')).status_code==400
    assert b'Synthetic observed context' not in client.get('/med/continuity').data
    assert b'Synthetic observed context' in client.get('/med/continuity?history=1').data


def test_invalid_owner_and_actions_and_get_is_read_only(env):
    approve(env);create_event(env)
    e=event();client=as_user(env,'dr')
    for action in ['assign','escalate']:
        assert client.post(f'/med/continuity/{e.id}',data=dict(action=action,detail='Test',owner_id=env[1]['foreign'].id)).status_code==400
    assert client.post(f'/med/continuity/{e.id}',data=dict(action='diagnose',detail='No')).status_code==400
    before=db.session.scalar(select(func.count(ContinuityHistory.id)))
    for path in ['/med/continuity','/med/continuity?history=1',f'/med/continuity/{e.id}',
                 f'/med/patients/{e.patient_id}/care-plan']:
        assert client.get(path).status_code==200
    assert db.session.scalar(select(func.count(ContinuityHistory.id)))==before and e.state=='open'


def test_sandbox_notification_neutral_dedup_and_latest_consent(env):
    approve(env);create_event(env)
    e=event();client=as_user(env,'dr')
    form=dict(action='sandbox_notification',detail='PRIVATE relapse text must not appear',channel='phone')
    for _ in range(2):assert client.post(f'/med/continuity/{e.id}',data=form).status_code==302
    n=db.session.scalar(select(ContinuityNotification))
    assert n.mode=='sandbox' and 'relapse' not in n.body and 'PRIVATE' not in n.body
    assert db.session.scalar(select(func.count(ContinuityNotification.id)))==1
    assert all('PRIVATE' not in h.detail for h in e.history)
    form['channel']='email'
    assert client.post(f'/med/continuity/{e.id}',data=form).status_code==400
    new_form=plan_form(env);new_form['communication_consent']='no'
    client.post(f'/med/patients/{env[2][0].id}/care-plan',data=new_form)
    form['channel']='portal'
    assert client.post(f'/med/continuity/{e.id}',data=form).status_code==400
    assert db.session.scalar(select(func.count(ContinuityNotification.id)))==1


def test_administrative_sources_verified_and_reschedule_archives(env):
    approve(env)
    a=env[3][0]
    assert create_event(env,'missed_appointment',appointment_id=a.id).status_code==400
    assert create_event(env,'unconfirmed_booking',appointment_id=env[3][1].id).status_code==400
    for kind in ['unconfirmed_booking','failed_reminder']:
        assert create_event(env,kind,appointment_id=a.id).status_code==302
    es=list(db.session.scalars(select(ContinuityEvent)))
    client=as_user(env,'dr')
    assert client.post(f'/med/appointments/{a.id}/status',data={'status':'scheduled'}).status_code==302
    assert all(e.state=='open' for e in es)  # saving an unchanged status is not resolution
    from test_calendar import approved,utc_on,time
    _,day=approved(env[2][0])
    assert client.post(f'/med/appointments/{a.id}/reschedule',data={
        'starts_at':local(utc_on(day,time(9,10))),'version':a.schedule_version,'confirmed':'yes','reason':'Agreed time change'}).status_code==302
    assert all(e.state=='archived' for e in es) and a.status=='scheduled'
    assert all('schedule updated' in e.history[-1].detail for e in es)
    assert len(list(db.session.scalars(select(Appointment).where(Appointment.patient_id==a.patient_id))))==1


def test_overdue_review_requires_elapsed_approved_review_and_new_plan_archives(env):
    p=approve(env)
    assert create_event(env,'overdue_followup').status_code==400
    p.review_at=utcnow()-timedelta(minutes=1);db.session.commit()  # synthetic elapsed clock
    create_event(env,'overdue_followup');e=event()
    assert e.category=='administrative' and e.state=='open'
    create_event(env,'overdue_followup')
    assert db.session.scalar(select(func.count(ContinuityEvent.id)))==1
    approve(env)
    assert e.state=='archived'


def test_csrf_and_authentication_for_continuity(env):
    approve(env);create_event(env)
    e=event();app=env[0];app.config['WTF_CSRF_ENABLED']=True
    client=as_user(env,'dr')
    for path in ['/med/continuity/events',f'/med/continuity/{e.id}',
                 f'/med/patients/{e.patient_id}/care-plan',f'/med/appointments/{env[3][0].id}/reschedule']:
        assert client.post(path,data={}).status_code==400
    assert as_user(env,'patient').post('/med/check-in',data={}).status_code==400
    app.config['WTF_CSRF_ENABLED']=False
    g.pop('_login_user', None)  # fixture keeps an application context across test clients
    assert app.test_client().get('/med/continuity').status_code==302
    assert as_user(env,'edu').get('/med/continuity').status_code==403
    assert as_user(env,'edu').post('/med/continuity/events',data={}).status_code==403


def test_database_rejects_category_conversion_and_duplicate_live_alert(env):
    from sqlalchemy.exc import IntegrityError
    approve(env);create_event(env)
    e=event();e.category='administrative'
    with pytest.raises(IntegrityError):db.session.flush()
    db.session.rollback()
    original=event()
    duplicate=ContinuityEvent(institution_id=original.institution_id,patient_id=original.patient_id,
        plan_id=original.plan_id,author_id=original.author_id,owner_id=original.owner_id,
        category=original.category,kind=original.kind,source_key=original.source_key,
        reason='Duplicate',due_at=original.due_at,state='open')
    db.session.add(duplicate)
    with pytest.raises(IntegrityError):db.session.flush()
    db.session.rollback()
    assert event().category=='clinical'


def test_reschedule_collision_rolls_back_and_cross_scope_rejected(env):
    approve(env)
    a=env[3][0]
    create_event(env,'failed_reminder',appointment_id=a.id)
    e=event()
    occupied=Appointment(patient_id=a.patient_id,doctor_id=a.doctor_id,
        starts_at=a.starts_at+timedelta(days=1),service=a.service,status='scheduled')
    db.session.add(occupied);db.session.commit()
    client=as_user(env,'dr')
    assert client.post(f'/med/appointments/{a.id}/reschedule',data={'starts_at':local(occupied.starts_at),'version':a.schedule_version,'confirmed':'yes','reason':'Agreed'}).status_code==302
    assert a.status=='scheduled' and e.state=='open'
    assert db.session.scalar(select(func.count(Appointment.id)))==4
    assert client.post(f'/med/appointments/{env[3][1].id}/reschedule',data={'starts_at':local(occupied.starts_at)}).status_code==404
    assert as_user(env,'patient').post(f'/med/appointments/{a.id}/reschedule',data={}).status_code==403
