import re
from datetime import timedelta, datetime
import pytest
from flask import g
from sqlalchemy import select
from app import create_app
from extensions import db
from models import User, Institution, Membership, Patient, CareAssignment, Appointment, Admission, BookingRequest, AuditEvent
from medical_services import utcnow, statistics


@pytest.fixture
def env():
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test-only-secret',
        'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'SQLALCHEMY_ENGINE_OPTIONS': {},
        'WTF_CSRF_ENABLED': False})
    with app.app_context():
        db.create_all()
        medical = Institution(name='Test medical A', kind='medical')
        other = Institution(name='Test medical B', kind='medical')
        education = Institution(name='Test education', kind='education')
        db.session.add_all([medical, other, education]); db.session.flush()
        users = {}
        for role in ['admin','dr','dr2','nurse','dr_assist','patient','otherpatient','foreign','edu']:
            u = User(name='Test '+role, email=role+'@example.test'); u.set_password('Testing-password-123')
            db.session.add(u); db.session.flush(); users[role] = u
            inst = other if role == 'foreign' else education if role == 'edu' else medical
            assigned_role = 'dr' if role in ['dr2','foreign'] else 'patient' if role=='otherpatient' else 'admin' if role=='edu' else role
            db.session.add(Membership(user_id=u.id,institution_id=inst.id,role=assigned_role,
                supervising_doctor_id=users['dr'].id if role=='dr_assist' else None))
        db.session.flush()
        p1 = Patient(name='Visible Patient',institution_id=medical.id,doctor_id=users['dr'].id,user_id=users['patient'].id)
        p2 = Patient(name='Other Doctor Patient',institution_id=medical.id,doctor_id=users['dr2'].id,user_id=users['otherpatient'].id)
        p3 = Patient(name='FOREIGN PRIVATE PATIENT',institution_id=other.id,doctor_id=users['foreign'].id)
        db.session.add_all([p1,p2,p3]); db.session.flush()
        db.session.add(CareAssignment(patient_id=p1.id,nurse_id=users['nurse'].id))
        now=utcnow().replace(minute=0,second=0,microsecond=0)
        a1=Appointment(patient_id=p1.id,doctor_id=p1.doctor_id,starts_at=now+timedelta(days=1),service='Individual therapy',status='scheduled')
        a2=Appointment(patient_id=p2.id,doctor_id=p2.doctor_id,starts_at=now+timedelta(days=1),service='Individual therapy',status='scheduled')
        a3=Appointment(patient_id=p3.id,doctor_id=p3.doctor_id,starts_at=now+timedelta(days=1),service='General consultation',status='scheduled')
        adm=Admission(patient_id=p1.id,facility='Test Facility',admitted_at=now-timedelta(days=1))
        db.session.add_all([a1,a2,a3,adm]); db.session.commit()
        yield app, users, [p1,p2,p3], [a1,a2,a3], adm
        db.session.remove(); db.drop_all()


def as_user(env, role):
    g.pop("_login_user", None)
    app,users,*_=env
    client=app.test_client()
    with client.session_transaction() as session:
        session['_user_id']=users[role].get_id(); session['_fresh']=True
    return client


@pytest.mark.parametrize('role',['admin','dr','nurse','dr_assist','patient'])
def test_each_role_dashboard(env,role):
    r=as_user(env,role).get('/med')
    assert r.status_code==200
    assert b'FOREIGN PRIVATE PATIENT' not in r.data
    if role=='patient':
        assert b'Other Doctor Patient' not in r.data
        assert b'Active patients' not in r.data
        assert b'Your next appointment'.upper() in r.data


@pytest.mark.parametrize('role',['dr','nurse','dr_assist'])
def test_staff_assignment_scope(env,role):
    client=as_user(env,role)
    assert client.get('/med/patients').status_code==200
    assert b'Visible Patient' in client.get('/med/patients').data
    assert b'Other Doctor Patient' not in client.get('/med/patients').data
    for patient in env[2][1:]:
        assert client.get(f'/med/patients/{patient.id}').status_code==404


@pytest.mark.parametrize('path',['/med/patients','/med/patients/1','/med/admissions','/admin/users','/admin/audit','/admin/requests'])
def test_patient_cannot_open_staff_views(env,path):
    assert as_user(env,'patient').get(path).status_code==403


@pytest.mark.parametrize('role',['dr','nurse','dr_assist','patient'])
def test_non_admin_cannot_manage_users(env,role):
    client=as_user(env,role)
    assert client.get('/admin/users').status_code==403
    assert client.post('/admin/users',data={}).status_code==403


def test_admin_only_current_institution(env):
    client=as_user(env,'admin')
    body=client.get('/med/patients').data
    assert b'Visible Patient' in body and b'Other Doctor Patient' in body
    assert b'FOREIGN PRIVATE PATIENT' not in body
    assert client.get(f'/med/patients/{env[2][2].id}').status_code==404
    assert client.post('/institutions',data={'institution_id':env[2][2].institution_id}).status_code==403


def test_education_membership_grants_no_medical_access(env):
    client=as_user(env,'edu')
    assert b'Education, coming later' in client.get('/med').data
    for path in ['/med/patients','/med/appointments','/med/admissions','/admin/users']:
        assert client.get(path).status_code==403


def test_patient_appointments_are_own_only(env):
    client=as_user(env,'patient')
    r=client.get('/med/appointments')
    assert r.status_code==200
    assert len(re.findall(b'class="status scheduled"',r.data))==1
    assert client.post(f'/med/appointments/{env[3][0].id}/status',data={'status':'cancelled'}).status_code==403


def test_out_of_scope_mutations_rejected(env):
    client=as_user(env,'dr')
    foreign=env[3][1]
    assert client.post(f'/med/appointments/{foreign.id}/status',data={'status':'cancelled'}).status_code==404
    assert client.post('/med/admissions',data={'patient_id':env[2][1].id,'facility':'Hospital'}).status_code==404
    assert foreign.status=='scheduled'


def test_future_completion_rejected(env):
    r=as_user(env,'dr').post(f'/med/appointments/{env[3][0].id}/status',data={'status':'completed'},follow_redirects=True)
    assert b'future appointment cannot' in r.data
    assert env[3][0].status=='scheduled'


def test_assistant_cannot_mark_seen_or_admit(env):
    client=as_user(env,'dr_assist')
    assert client.post(f'/med/appointments/{env[3][0].id}/status',data={'status':'completed'}).status_code==403
    assert client.post('/med/admissions',data={'patient_id':env[2][0].id,'facility':'Hospital'}).status_code==403
    assert client.post(f'/med/admissions/{env[4].id}/discharge').status_code==403


def test_nurse_can_discharge_only_assigned(env):
    client=as_user(env,'nurse')
    assert client.post(f'/med/admissions/{env[4].id}/discharge').status_code==302
    assert env[4].discharged_at is not None
    assert client.post('/med/admissions',data={'patient_id':env[2][1].id,'facility':'Hospital'}).status_code==404


def test_duplicate_open_admission_rejected(env):
    client=as_user(env,'dr')
    r=client.post('/med/admissions',data={'patient_id':env[2][0].id,'facility':'Another Facility'},follow_redirects=True)
    assert b'already has an open admission' in r.data
    assert db.session.scalar(select(db.func.count(Admission.id)))==1


def test_statistics_distinct_boundary_and_never_seen(env):
    now=datetime(2026,11,14,12)
    ps=env[2]
    # Exactly 90 days is active; 90 days plus one microsecond is inactive.
    for patient,days,delta in [(ps[0],90,0),(ps[1],90,1)]:
        db.session.add(Appointment(patient_id=patient.id,doctor_id=patient.doctor_id,
            starts_at=now-timedelta(days=days,microseconds=delta),status='completed',service='General consultation'))
    # More historical appointments must not inflate counts; future completed data is ignored.
    db.session.add(Appointment(patient_id=ps[0].id,doctor_id=ps[0].doctor_id,
        starts_at=now-timedelta(days=150),status='completed',service='General consultation'))
    db.session.add(Appointment(patient_id=ps[2].id,doctor_id=ps[2].doctor_id,
        starts_at=now+timedelta(days=5),status='completed',service='General consultation'))
    db.session.commit()
    stats,_,_=statistics(ps,now=now)
    assert stats=={'total':3,'active':1,'inactive':1,'never_seen':1,'admitted':1}


def test_cancelled_and_no_show_not_seen(env):
    a=env[3][0];a.starts_at=utcnow()-timedelta(days=1);a.status='no_show';db.session.commit()
    assert statistics([env[2][0]])[0]['never_seen']==1
    a.status='cancelled';db.session.commit()
    assert statistics([env[2][0]])[0]['active']==0


def test_doctor_slot_collision_and_cancelled_reuse(env):
    client=as_user(env,'dr')
    p=Patient(name='Same doctor',institution_id=env[2][0].institution_id,doctor_id=env[1]['dr'].id)
    db.session.add(p);db.session.commit()
    local=(env[3][0].starts_at+timedelta(hours=2)).isoformat(timespec='minutes')
    form={'patient_id':p.id,'starts_at':local,'service':'Individual therapy'}
    response=client.post('/med/appointments',data=form,follow_redirects=True)
    assert b'already has this slot' in response.data
    env[3][0].status='cancelled';db.session.commit()
    response=client.post('/med/appointments',data=form,follow_redirects=True)
    assert b'Appointment scheduled.' in response.data


def test_suspended_membership_stops_existing_session(env):
    client=as_user(env,'dr')
    member=db.session.scalar(select(Membership).where(Membership.user_id==env[1]['dr'].id))
    member.enabled=False;db.session.commit()
    assert client.get('/med/patients').status_code==403


def test_suspended_supervisor_stops_assistant_data(env):
    member=db.session.scalar(select(Membership).where(Membership.user_id==env[1]['dr'].id))
    member.enabled=False;db.session.commit()
    r=as_user(env,'dr_assist').get('/med/patients')
    assert b'Visible Patient' not in r.data


def test_password_reset_invalidates_existing_session(env):
    client=as_user(env,'dr')
    env[1]['dr'].set_password('New-test-password-456');db.session.commit()
    assert client.get('/med/patients').status_code==302


def test_csrf_and_post_only_logout(env):
    app=env[0];app.config['WTF_CSRF_ENABLED']=True
    client=app.test_client()
    assert client.post('/auth/login',data={'email':'dr@example.test','password':'Testing-password-123'}).status_code==400
    assert client.get('/auth/logout').status_code==405
    body=client.get('/auth/login').data
    token=re.search(rb'name="csrf_token" value="([^"]+)"',body).group(1).decode()
    response=client.post('/auth/login',data={'csrf_token':token,'email':'dr@example.test','password':'Testing-password-123'})
    assert response.status_code==302
    assert client.post('/med/admissions',data={}).status_code==400


def test_login_failure_generic_and_account_lock(env):
    client=env[0].test_client()
    for _ in range(5):
        assert b'Unable to sign in' in client.post('/auth/login',data={'email':'dr@example.test','password':'wrong'}).data
    assert env[1]['dr'].locked_until is not None
    r=client.post('/auth/login',data={'email':'dr@example.test','password':'Testing-password-123'})
    assert b'Unable to sign in' in r.data


def test_public_request_validates_and_stores_no_notes(env):
    client=env[0].test_client()
    form={'full_name':'Test Person','email':'test@example.test','phone':'000 000 0000',
        'service_type':'Individual therapy','preferred_at':(utcnow()+timedelta(days=2,hours=2)).isoformat(timespec='minutes')}
    assert client.post('/book',data=form).status_code==400
    form['consent']='on';form['notes']='Should not be collected'
    assert client.post('/book',data=form).status_code==302
    saved=db.session.scalar(select(BookingRequest))
    assert saved and not hasattr(saved,'notes')
    assert as_user(env,'patient').get('/admin/requests').status_code==403


def test_admin_cannot_claim_existing_account(env):
    old=env[1]['foreign'].password_hash
    r=as_user(env,'admin').post('/admin/users',data={'name':'Changed','email':'foreign@example.test',
        'password':'Changed-password-999','role':'admin'},follow_redirects=True)
    assert b'account already exists' in r.data
    assert env[1]['foreign'].password_hash==old


def test_admin_can_link_existing_patient(env):
    p=env[2][1];p.user_id=None;db.session.commit()
    r=as_user(env,'admin').post('/admin/users',data={'name':'Linked Person','email':'linked@example.test',
        'password':'Initial-password-123','role':'patient','doctor_id':p.doctor_id,'patient_id':p.id})
    assert r.status_code==302
    assert p.user_id is not None
    assert len(list(db.session.scalars(select(Patient).where(Patient.institution_id==p.institution_id))))==2


def test_administrator_can_render_all_views(env):
    client=as_user(env,'admin')
    for path in ['/med','/med/patients','/med/appointments','/med/admissions','/admin/users','/admin/requests','/admin/audit','/institutions',f'/med/patients/{env[2][0].id}']:
        assert client.get(path).status_code==200,path


def test_private_pages_no_store_and_security_headers(env):
    r=as_user(env,'patient').get('/med')
    assert r.headers['Cache-Control']=='no-store'
    assert r.headers['X-Frame-Options']=='DENY'
    assert "form-action 'self'" in r.headers['Content-Security-Policy']


def test_unauthenticated_cannot_mutate_medical_data(env):
    assert env[0].test_client().post('/med/admissions',data={}).status_code==302


def test_production_rejects_insecure_defaults(monkeypatch):
    monkeypatch.setenv('APP_ENV','production');monkeypatch.delenv('FLASK_SECRET_KEY',raising=False)
    from config import settings
    with pytest.raises(RuntimeError):settings()


def test_assistant_cannot_rewrite_completed_history(env):
    a=env[3][0];a.starts_at=utcnow()-timedelta(days=1);a.status='completed';db.session.commit()
    client=as_user(env,'dr_assist')
    assert client.post(f'/med/appointments/{a.id}/status',data={'status':'scheduled'}).status_code==403
    assert a.status=='completed'
    assert b'Doctor recorded' in client.get('/med/appointments').data


def test_disabled_supervisor_account_stops_assistant_data(env):
    env[1]['dr'].enabled=False;db.session.commit()
    r=as_user(env,'dr_assist').get('/med/patients')
    assert r.status_code==200
    assert b'Visible Patient' not in r.data
