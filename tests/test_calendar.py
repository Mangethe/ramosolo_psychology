"""Synthetic operational scheduling regression cases. No delivery networks."""
from datetime import datetime, time, timedelta, timezone
import pytest
from sqlalchemy import select, func
from test_medical import env, as_user
from extensions import db
from models import (Appointment, AvailabilityPolicy, AvailabilitySession, AvailabilityException,
    PublicHoliday, CalendarBlock, CalendarDelegation, AppointmentProposal, CalendarHistory, CommunicationDecision)
from scheduling_services import available_slots, local_day, utc_on
from medical_services import utcnow, TZ


def local(value):
    return value.replace(tzinfo=timezone.utc).astimezone(TZ).isoformat(timespec='minutes')


def approved(patient):
    policy=AvailabilityPolicy(institution_id=patient.institution_id,doctor_id=patient.doctor_id,
        enabled=True,holidays_confirmed=True,daily_limit=5,horizon_days=90)
    db.session.add(policy);db.session.flush()
    for day,care,duration in [(2,'outpatient',30),(0,'inpatient',20),(1,'inpatient',20),(2,'inpatient',20),(4,'inpatient',20)]:
        db.session.add(AvailabilitySession(policy_id=policy.id,weekday=day,care_type=care,
            opens_at=time(8),closes_at=time(17),duration_minutes=duration,first_minutes=60,
            assessment_minutes=90,break_minutes=5))
    db.session.commit()
    day=local_day(utcnow())+timedelta(days=7)
    while day.weekday()!=2:day+=timedelta(days=1)
    return policy,day


@pytest.fixture
def calendar_env(env):
    p=env[2][0];policy,day=approved(p)
    a=env[3][0];a.starts_at=utc_on(day,time(8));a.ends_at=a.starts_at+timedelta(minutes=30)
    a.occupied_until=a.ends_at+timedelta(minutes=5);a.care_type='outpatient';a.visit_kind='followup'
    db.session.commit()
    return env,policy,day


def proposal(env,day):
    a=env[3][0]
    r=as_user(env,'dr_assist').post(f'/med/calendar/{a.id}/propose',data={
        'version':a.schedule_version,'reason':'Patient requested time change','starts_at':local(utc_on(day,time(9,10)))})
    assert r.status_code==302
    return db.session.scalar(select(AppointmentProposal).order_by(AppointmentProposal.id.desc()))


@pytest.mark.parametrize('role,code',[('dr',200),('dr_assist',200),('admin',200),('nurse',403),('patient',403),('edu',403)])
def test_calendar_roles_and_scoped_view(calendar_env,role,code):
    env,_,_=calendar_env
    response=as_user(env,role).get('/med/calendar')
    assert response.status_code==code
    assert b'FOREIGN PRIVATE PATIENT' not in response.data
    if role in ('dr','dr_assist'):assert b'Other Doctor Patient' not in response.data


def test_same_engine_collision_duration_capacity_closures(calendar_env):
    env,policy,day=calendar_env;p=env[2][0]
    slots=available_slots(p,day)
    assert slots[0][0]==utc_on(day,time(8,35))  # 30 minutes plus five minute break
    assert available_slots(p,day+timedelta(days=1))==[]
    assert available_slots(p,day+timedelta(days=1),'inpatient')==[]
    assert available_slots(p,day,'outpatient','first')[0][1]-available_slots(p,day,'outpatient','first')[0][0]==timedelta(hours=1)
    policy.daily_limit=1;db.session.commit();assert available_slots(p,day)==[]
    policy.daily_limit=5
    db.session.add(PublicHoliday(institution_id=p.institution_id,day=day,label='Synthetic holiday'));db.session.commit()
    assert available_slots(p,day)==[]


def test_policy_fail_closed_and_no_identity_leak(env):
    p=env[2][0]
    assert available_slots(p,local_day(utcnow())+timedelta(days=7))==[]
    r=as_user(env,'dr_assist').get('/med/calendar/availability',query_string={'patient_id':p.id,'day':'2026-12-02'})
    assert r.status_code==200 and b'Other Doctor Patient' not in r.data and b'FOREIGN' not in r.data
    for p in env[2][1:]:assert as_user(env,'dr_assist').get('/med/calendar/availability',query_string={'patient_id':p.id,'day':'2026-12-02'}).status_code==404


def test_proposal_accept_preserves_id_and_original_until_acceptance(calendar_env):
    env,_,day=calendar_env;a=env[3][0];original=a.starts_at
    p=proposal(env,day);assert p and a.starts_at==original and a.status=='scheduled'
    url=f'/med/calendar/proposals/{p.token_digest}/respond'
    member_url = f'/med/calendar/proposals/{p.id}/respond'
    listing = as_user(env, 'patient').get('/med/appointments')
    assert member_url.encode() in listing.data and p.token_digest.encode() not in listing.data
    assert as_user(env, 'otherpatient').get(member_url).status_code == 404
    assert as_user(env,'otherpatient').post(url,data={'decision':'accepted'}).status_code==404
    assert as_user(env,'patient').get(url).status_code==200 and p.state=='pending'
    assert as_user(env,'patient').post(member_url,data={'decision':'accepted'}).status_code==200
    assert a.starts_at==p.proposed_at and a.schedule_version==2 and p.state=='accepted'
    assert db.session.scalar(select(func.count(Appointment.id)))==3
    assert as_user(env,'patient').post(url,data={'decision':'accepted'}).status_code==409
    h=db.session.scalar(select(CalendarHistory).where(CalendarHistory.action=='proposal_accepted'))
    assert h.original_at==original and h.new_at==p.proposed_at and h.actor_id==env[1]['patient'].id


def test_decline_expiry_supersession_no_implicit_hold(calendar_env):
    env,_,day=calendar_env;a=env[3][0];original=a.starts_at
    p=proposal(env,day)
    assert p.proposed_at in [s[0] for s in available_slots(env[2][0],day)]
    assert as_user(env,'patient').post(f'/med/calendar/proposals/{p.token_digest}/respond',data={'decision':'declined'}).status_code==200
    assert p.state=='declined' and a.starts_at==original
    p=proposal(env,day);p.expires_at=utcnow()-timedelta(seconds=1);db.session.commit()
    assert as_user(env,'patient').get(f'/med/calendar/proposals/{p.token_digest}/respond').status_code==200
    assert p.state=='pending'  # GET has no operational side effects
    assert as_user(env,'patient').post(f'/med/calendar/proposals/{p.token_digest}/respond',data={'decision':'accepted'}).status_code==410
    assert p.state=='expired' and a.starts_at==original
    p=proposal(env,day);new=proposal(env,day);assert p.state=='superseded' and new.state=='pending'


def test_slot_taken_after_proposal_and_stale_form(calendar_env):
    env,_,day=calendar_env;a=env[3][0];p=proposal(env,day)
    occupied=Appointment(patient_id=env[2][0].id,doctor_id=a.doctor_id,starts_at=p.proposed_at,
        ends_at=p.proposed_at+timedelta(minutes=30),status='scheduled',service='General consultation')
    db.session.add(occupied);db.session.commit()
    original=a.starts_at
    assert as_user(env,'patient').post(f'/med/calendar/proposals/{p.token_digest}/respond',data={'decision':'accepted'}).status_code==409
    assert a.starts_at==original and p.state=='pending'
    assert as_user(env,'dr_assist').post(f'/med/appointments/{a.id}/reschedule',data={'version':0,
        'confirmed':'yes','reason':'Agreed','starts_at':local(utc_on(day,time(10,20)))}).status_code==409


def test_admin_blocks_require_delegation_and_respect_appointments(calendar_env):
    env,_,day=calendar_env;doctor=env[1]['dr'].id;assistant=env[1]['dr_assist'].id
    form={'doctor_id':doctor,'starts_at':local(utc_on(day,time(12,5))),'ends_at':local(utc_on(day,time(13)))}
    client=as_user(env,'dr_assist');assert client.post('/med/calendar/blocks',data=form).status_code==403
    db.session.add(CalendarDelegation(institution_id=env[2][0].institution_id,doctor_id=doctor,
        assistant_id=assistant,enabled=True,expires_at=utcnow()+timedelta(days=30)));db.session.commit()
    assert client.post('/med/calendar/blocks',data=form).status_code==302
    row=db.session.scalar(select(CalendarBlock));assert row.reason=='administration'
    assert utc_on(day,time(12,5)) not in [s[0] for s in available_slots(env[2][0],day)]
    assert client.post(f'/med/calendar/blocks/{row.id}/release').status_code==302
    form['starts_at']=local(env[3][0].starts_at);assert client.post('/med/calendar/blocks',data=form).status_code==409


@pytest.mark.parametrize('status',['completed','no_show','scheduled'])
def test_assistant_cannot_change_attendance_or_past(calendar_env,status):
    env,_,day=calendar_env;a=env[3][0];a.starts_at=utcnow()-timedelta(days=1);a.status=status;db.session.commit()
    assert as_user(env,'dr_assist').post(f'/med/appointments/{a.id}/status',data={'status':'cancelled','version':a.schedule_version}).status_code==403
    assert as_user(env,'dr_assist').post(f'/med/calendar/{a.id}/propose',data={'version':a.schedule_version,'reason':'Agreed','starts_at':local(utc_on(day,time(9,10)))}).status_code==403


def test_future_cancellation_invalidates_proposal(calendar_env):
    env,_,day=calendar_env;a=env[3][0];p=proposal(env,day);client=as_user(env,'dr_assist')
    assert client.post(f'/med/appointments/{a.id}/status',data={'status':'cancelled','version':0}).status_code==409
    assert client.post(f'/med/appointments/{a.id}/status',data={'status':'cancelled','version':1}).status_code==302
    assert a.status=='cancelled' and p.state=='superseded'


def test_cancellation_leaves_legacy_proposal_from_another_institution_untouched(calendar_env):
    env, _, day = calendar_env
    appointment = env[3][0]
    pending = proposal(env, day)
    pending.institution_id = env[2][2].institution_id
    db.session.commit()

    client = as_user(env, 'dr')
    assert client.post(f'/med/appointments/{appointment.id}/status',
        data={'status': 'cancelled', 'version': appointment.schedule_version}).status_code == 302
    assert appointment.status == 'cancelled'
    assert pending.state == 'pending' and pending.responded_at is None


def test_guest_opaque_link_code_consent_and_synthetic_delivery(calendar_env):
    env,_,day=calendar_env;patient=env[2][0];patient.user_id=None
    sink=[];env[0].config['CALENDAR_SYNTHETIC_DELIVERIES']=sink
    consent=CommunicationDecision(institution_id=patient.institution_id,patient_id=patient.id,purpose='administrative_contact',
        channel='email',scope='practice',status='granted',destination='synthetic@example.test',verified_at=utcnow(),
        verified_by_id=env[1]['dr'].id,timezone='Africa/Johannesburg',method='Synthetic verification',notice_version='test-v1',recorded_by_id=env[1]['dr'].id)
    db.session.add(consent);db.session.commit();p=proposal(env,day);assert len(sink)==1
    delivered=sink[0];url='/calendar-change/'+delivered['token'];client=env[0].test_client()
    r=client.get(url);assert r.status_code==200 and b'Visible Patient' not in r.data
    assert r.headers['Cache-Control']=='no-store' and r.headers['Referrer-Policy']=='strict-origin'
    assert client.post(url,data={'code':'wrong','decision':'accepted'}).status_code==403
    assert client.post(url,data={'code':delivered['code'],'decision':'review'}).status_code==200
    assert p.state=='pending'
    assert client.post(url,data={'code':delivered['code'],'decision':'accepted'}).status_code==200
    assert p.state=='accepted'


def test_new_forms_csrf_and_get_readonly(calendar_env):
    env,_,day=calendar_env;env[0].config['WTF_CSRF_ENABLED']=True;client=as_user(env,'dr_assist')
    for path in ['/med/calendar/blocks','/med/calendar/1/propose','/med/calendar/delegations','/calendar-change/test']:
        assert client.post(path).status_code==400
    assert client.get('/med/calendar').status_code==200


def test_leave_blocks_breaks_and_inpatient_duration(calendar_env):
    env,policy,day=calendar_env;p=env[2][0]
    slots=available_slots(p,day,'inpatient')
    assert slots[0][1]-slots[0][0]==timedelta(minutes=20)
    assert slots[1][0]-slots[0][0]==timedelta(minutes=25)
    db.session.add(AvailabilityException(policy_id=policy.id,day=day,kind='leave',approved_by=env[1]['dr'].id,reason='Synthetic leave'))
    db.session.commit();assert available_slots(p,day)==[]
    db.session.add(AvailabilityException(policy_id=policy.id,day=day,kind='opening',care_type='outpatient',
        opens_at=time(12),closes_at=time(14),duration_minutes=30,first_minutes=60,assessment_minutes=90,
        break_minutes=5,override_closure=True,approved_by=env[1]['dr'].id,reason='Synthetic approved exception'))
    db.session.commit();assert available_slots(p,day)[0][0]==utc_on(day,time(12))


def test_guest_unverified_and_withdrawal_suppress_delivery_and_response(calendar_env):
    env,_,day=calendar_env;p=env[2][0];p.user_id=None;db.session.commit()
    sink=[];env[0].config['CALENDAR_SYNTHETIC_DELIVERIES']=sink
    assert proposal(env,day) and sink==[]
    decision=CommunicationDecision(institution_id=p.institution_id,patient_id=p.id,purpose='administrative_contact',
        channel='email',scope='practice',status='granted',destination='guest@example.test',verified_at=utcnow(),
        verified_by_id=env[1]['dr'].id,timezone='Africa/Johannesburg',method='Synthetic',notice_version='v1',recorded_by_id=env[1]['dr'].id)
    db.session.add(decision);db.session.commit();prop=proposal(env,day);assert len(sink)==1
    db.session.add(CommunicationDecision(institution_id=p.institution_id,patient_id=p.id,purpose='administrative_contact',
        channel='email',scope='practice',status='withdrawn',destination='',timezone='Africa/Johannesburg',
        method='Synthetic',notice_version='v1',recorded_by_id=env[1]['dr'].id));db.session.commit()
    r=env[0].test_client().post('/calendar-change/'+sink[0]['token'],data={'code':sink[0]['code'],'decision':'accepted'})
    assert r.status_code==403 and prop.state=='pending'


def test_reminders_replaced_by_version_without_real_delivery(calendar_env):
    import json
    from pathlib import Path
    from sqlalchemy import Table,Column,MetaData,Integer,Boolean,DateTime,String
    from scheduling_services import refresh_reminders
    env,_,day=calendar_env;a=env[3][0];p=env[2][0]
    meta=MetaData();tables={}
    shapes=json.loads(Path('verification/live-schema-metadata.json').read_text(encoding='utf-8'))['columns']
    for name in ['reminder_policies','reminder_leads','communication_preferences','notification_outbox']:
        columns=[]
        for column in shapes:
            if column['table_name']!=name:continue
            kind={'integer':Integer,'boolean':Boolean,'timestamp without time zone':DateTime}.get(column['data_type'],String)
            columns.append(Column(column['column_name'],kind,primary_key=column['column_name']=='id'))
        tables[name]=Table(name,meta,*columns)
    meta.create_all(db.session.connection())
    pref=tables['communication_preferences'];policy=tables['reminder_policies'];leads=tables['reminder_leads'];outbox=tables['notification_outbox']
    db.session.execute(pref.insert().values(id=1,institution_id=p.institution_id,patient_id=p.id,
        in_app_enabled=True,in_app_consent_at=utcnow(),version=1,email_enabled=False,sms_enabled=False,changed_at=utcnow()))
    db.session.execute(policy.insert().values(id=1,institution_id=p.institution_id,enabled=True,version=1,
        max_attempts=3,retry_seconds=60,link_minutes=30,catchup_minutes=10,updated_by=env[1]['dr'].id,updated_at=utcnow()))
    db.session.execute(leads.insert().values(id=1,policy_id=1,minutes=60));db.session.commit()
    as_user(env,'dr').get('/med')  # scoped request context for consent checks
    refresh_reminders(a);db.session.commit()
    first=db.session.execute(select(outbox)).mappings().one()
    assert first['state']=='pending' and first['appointment_version']==1 and first['channel']=='in_app'
    prop=proposal(env,day)
    assert as_user(env,'patient').post(f'/med/calendar/proposals/{prop.token_digest}/respond',data={'decision':'accepted'}).status_code==200
    jobs=db.session.execute(select(outbox).order_by(outbox.c.id)).mappings().all()
    assert len(jobs)==2 and jobs[0]['state']=='cancelled' and jobs[1]['state']=='pending'
    assert jobs[1]['scheduled_start']==prop.proposed_at and jobs[1]['appointment_version']==2
    assert all(j['sent_at'] is None for j in jobs)
    refresh_reminders(a);db.session.commit()
    assert db.session.scalar(select(func.count()).select_from(outbox))==2


@pytest.mark.parametrize('role',['dr','dr_assist','admin','nurse','patient'])
def test_new_mutations_cross_institution_are_denied(calendar_env,role):
    env,_,day=calendar_env;foreign=env[3][2];client=as_user(env,role)
    form={'version':1,'reason':'Synthetic','confirmed':'yes','starts_at':local(utc_on(day,time(9,10)))}
    expected=404 if role in ('dr','dr_assist','admin') else 403
    assert client.post(f'/med/calendar/{foreign.id}/propose',data=form).status_code==expected
    assert client.post(f'/med/appointments/{foreign.id}/reschedule',data=form).status_code==expected
    assert foreign.schedule_version==1


def test_existing_holds_consume_slots_until_expiry(calendar_env):
    env,_,day=calendar_env;p=env[2][0];start=utc_on(day,time(9,10))
    held=Appointment(patient_id=p.id,doctor_id=p.doctor_id,starts_at=start,ends_at=start+timedelta(minutes=30),
        occupied_until=start+timedelta(minutes=35),status='held',service='General consultation',hold_expires_at=utcnow()+timedelta(minutes=10))
    db.session.add(held);db.session.commit();assert start not in [s[0] for s in available_slots(p,day)]
    held.hold_expires_at=utcnow()-timedelta(seconds=1);db.session.commit()
    assert start in [s[0] for s in available_slots(p,day)]


def test_completed_history_cannot_be_changed_even_with_future_timestamp(calendar_env):
    env,_,day=calendar_env;a=env[3][0]
    a.status='completed';db.session.commit();original=a.starts_at
    client=as_user(env,'dr_assist')
    form={'version':1,'confirmed':'yes','reason':'Synthetic attempted rewrite',
        'starts_at':local(utc_on(day,time(9,10)))}
    for path,data in [(f'/med/appointments/{a.id}/status',{'status':'cancelled','version':1}),
            (f'/med/appointments/{a.id}/reschedule',form),(f'/med/calendar/{a.id}/propose',form)]:
        assert client.post(path,data=data).status_code==403
    db.session.refresh(a)
    assert (a.status,a.starts_at,a.schedule_version)==('completed',original,1)


def test_guest_verification_code_is_bound_to_its_own_proposal(calendar_env,monkeypatch):
    from models import Patient
    import scheduling_services
    env,_,day=calendar_env;patient=env[2][0];patient.user_id=None
    other=Patient(institution_id=patient.institution_id,doctor_id=patient.doctor_id,name='Synthetic second guest')
    db.session.add(other);db.session.flush()
    second=Appointment(patient_id=other.id,doctor_id=other.doctor_id,starts_at=utc_on(day,time(10,20)),
        ends_at=utc_on(day,time(10,50)),occupied_until=utc_on(day,time(10,55)),
        care_type='outpatient',visit_kind='followup',service='General consultation',status='scheduled')
    db.session.add(second)
    for p in (patient,other):
        db.session.add(CommunicationDecision(institution_id=p.institution_id,patient_id=p.id,
            purpose='administrative_contact',channel='email',scope='practice',status='granted',
            destination=f'guest-{p.id}@example.test',verified_at=utcnow(),verified_by_id=env[1]['dr'].id,
            timezone='Africa/Johannesburg',method='Synthetic',notice_version='test',recorded_by_id=env[1]['dr'].id))
    db.session.commit()
    codes=iter((100001,100002));monkeypatch.setattr(scheduling_services.secrets,'randbelow',lambda limit:next(codes))
    sink=[];env[0].config['CALENDAR_SYNTHETIC_DELIVERIES']=sink
    first=proposal(env,day)
    assert as_user(env,'dr_assist').post(f'/med/calendar/{second.id}/propose',data={
        'version':1,'reason':'Synthetic change','starts_at':local(utc_on(day,time(12,5)))}).status_code==302
    assert len(sink)==2
    client=env[0].test_client()
    assert client.post('/calendar-change/'+sink[1]['token'],data={'code':sink[0]['code'],'decision':'accepted'}).status_code==403
    assert first.state=='pending' and second.schedule_version==1
    assert client.post('/calendar-change/'+sink[0]['token'],data={'code':sink[0]['code'],'decision':'accepted'}).status_code==200
    assert first.state=='accepted' and second.schedule_version==1
