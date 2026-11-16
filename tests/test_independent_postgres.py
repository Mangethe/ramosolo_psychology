"""Real local PostgreSQL 18 tests. Never accepts a live URL or imports credentials."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
import os
import socket
import subprocess
import tempfile
import threading
import uuid
import pytest
import psycopg
from psycopg import sql
from sqlalchemy import select, func, create_engine, inspect
from app import create_app
from extensions import db
from models import (User, Institution, Membership, Patient, CareAssignment, CarePlan,
                    Appointment, ContinuityEvent, ContinuityHistory, ClinicalRecord)
from medical_services import utcnow, TZ
from continuity_services import KINDS

ROOT=Path(__file__).resolve().parents[1]
BIN=Path('C:/Program Files/PostgreSQL/18/bin')


@pytest.fixture(scope='module')
def local_pg():
    if not (BIN/'initdb.exe').exists():
        pytest.skip('Local PostgreSQL 18 binaries unavailable; no remote fallback allowed')
    directory=Path(tempfile.mkdtemp(prefix='ramosolo-independent-',dir='C:/Temp'))
    data_directory=directory/'data'
    print('Starting isolated synthetic PostgreSQL cluster: '+str(directory),flush=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    def run(args):
        print('Synthetic PostgreSQL command: '+args[0]+' '+args[-1],flush=True)
        log=directory/'synthetic-command.log'
        with log.open('w',encoding='utf-8') as output:
            result=subprocess.run([str(BIN/args[0]),*args[1:]],stdout=output,stderr=subprocess.STDOUT,
                creationflags=flags,timeout=60)
        if result.returncode:
            pytest.fail('Isolated PostgreSQL command failed: '+log.read_text(encoding='utf-8',errors='replace'))
    run(['initdb.exe','-D',str(data_directory),'-U','qa_owner','-A','trust','--no-locale','--encoding=UTF8'])
    run(['pg_ctl.exe','-D',str(data_directory),'-l',str(directory/'synthetic-server.log'),'-o',
         f'-h 127.0.0.1 -p {port} -c shared_buffers=16MB -c max_connections=24','-w','start'])
    dsn=f'postgresql://qa_owner@127.0.0.1:{port}/postgres'
    try:
        with psycopg.connect(dsn,autocommit=True) as connection:
            connection.execute('CREATE ROLE anon NOLOGIN')
            connection.execute('CREATE ROLE authenticated NOLOGIN')
        yield dsn
    finally:
        run(['pg_ctl.exe','-D',str(data_directory),'-m','fast','-w','stop'])
        # Retain the synthetic cluster in C:/Temp; never recursively delete computed paths.


@pytest.fixture
def isolated_database(local_pg):
    name='qa_'+uuid.uuid4().hex
    with psycopg.connect(local_pg,autocommit=True) as connection:
        connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    dsn=local_pg.rsplit('/',1)[0]+'/'+name
    yield dsn
    # Entire database was created by this fixture, on the isolated loopback cluster.
    assert name.startswith('qa_') and '127.0.0.1:' in dsn
    with psycopg.connect(local_pg,autocommit=True) as connection:
        connection.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))


def migration(number):
    return next((ROOT/'migrations').glob(f'{number:03}_*.sql')).read_text(encoding='utf-8')


def test_new_database_migrations_match_orm_and_preserve_synthetic_existing_rows(isolated_database):
    with psycopg.connect(isolated_database,autocommit=True) as c:
        c.execute(migration(1))
        c.execute("INSERT INTO lesonto.institutions(name,kind) VALUES ('Synthetic migration sentinel','medical')")
        for version in (2,3):c.execute(migration(version))
        # Legacy local foundation plus the additive coordination upgrade in its local schema.
        c.execute('INSERT INTO lesonto.schema_versions(version) VALUES (4),(5),(6),(7)')
        c.execute(migration(8).replace('ramosolo','lesonto'))
        c.execute(migration(9).replace('ramosolo','lesonto'))
        assert c.execute('SELECT name FROM lesonto.institutions').fetchone()[0]=='Synthetic migration sentinel'
        assert c.execute('SELECT version FROM lesonto.schema_versions ORDER BY version').fetchall()==[(n,) for n in range(1,10)]
    engine=create_engine(isolated_database.replace('postgresql://','postgresql+psycopg://'),
        connect_args={'options':'-csearch_path=lesonto,public'},hide_parameters=True)
    try:
        actual=inspect(engine)
        for table in db.metadata.sorted_tables:
            columns={c['name']:c for c in actual.get_columns(table.name)}
            assert set(columns)==set(table.columns.keys()),table.name
            for column in table.columns:
                assert columns[column.name]['nullable']==column.nullable,(table.name,column.name)
    finally:engine.dispose()


def test_current_schema_name_and_migration_ledger_are_incompatible_without_reconciliation(isolated_database):
    with psycopg.connect(isolated_database,autocommit=True) as c:
        # Structural replay of the observed live schema name/version ledger, with no live rows.
        c.execute(migration(1).replace('lesonto','ramosolo'))
        c.execute('INSERT INTO ramosolo.schema_versions(version) VALUES (2),(3),(4),(5),(6)')
        c.execute("INSERT INTO ramosolo.institutions(name,kind) VALUES ('Synthetic preserved row','medical')")
        with pytest.raises(psycopg.errors.UndefinedTable):c.execute(migration(2))
        c.execute('ROLLBACK')
        # Changing only search_path still collides with already-used version 2.
        adapted=migration(2).replace('SET LOCAL search_path TO lesonto, public','SET LOCAL search_path TO ramosolo, public')
        with pytest.raises(psycopg.errors.UniqueViolation):c.execute(adapted)
        c.execute('ROLLBACK')
        assert c.execute("SELECT to_regclass('ramosolo.care_plans')").fetchone()[0] is None
        assert c.execute('SELECT name FROM ramosolo.institutions').fetchone()[0]=='Synthetic preserved row'
        assert c.execute('SELECT count(*) FROM ramosolo.schema_versions').fetchone()[0]==6


@pytest.fixture
def pg_case(isolated_database):
    app=create_app({'TESTING':True,'SECRET_KEY':'synthetic-pg-review',
        'SQLALCHEMY_DATABASE_URI':isolated_database.replace('postgresql://','postgresql+psycopg://'),
        'SQLALCHEMY_ENGINE_OPTIONS':{},'WTF_CSRF_ENABLED':False})
    with app.app_context():
        db.create_all()
        a=Institution(name='Synthetic A',kind='medical');b=Institution(name='Synthetic B',kind='medical')
        db.session.add_all([a,b]);db.session.flush()
        users={}
        for role in ('dr','dr2','nurse','dr_assist','admin','patient','foreign'):
            user=User(name='Synthetic '+role,email=role+'@independent.test',
                password_hash='synthetic-disabled-password-login',enabled=True,session_version=1)
            db.session.add(user);db.session.flush();users[role]=user
            db.session.add(Membership(user_id=user.id,institution_id=b.id if role=='foreign' else a.id,
                role='dr' if role in ('dr2','foreign') else role,
                supervising_doctor_id=users['dr'].id if role=='dr_assist' else None))
        p=Patient(institution_id=a.id,doctor_id=users['dr'].id,user_id=users['patient'].id,name='Synthetic assigned')
        peer=Patient(institution_id=a.id,doctor_id=users['dr2'].id,name='Synthetic peer')
        foreign=Patient(institution_id=b.id,doctor_id=users['foreign'].id,name='Synthetic foreign')
        same_dr=Patient(institution_id=a.id,doctor_id=users['dr'].id,name='Synthetic second assigned')
        db.session.add_all([p,peer,foreign,same_dr]);db.session.flush()
        db.session.add(CareAssignment(patient_id=p.id,nurse_id=users['nurse'].id))
        db.session.add(CarePlan(institution_id=a.id,patient_id=p.id,author_id=users['dr'].id,
            owner_id=users['dr'].id,goals='Synthetic goal',warning_signs='Synthetic signs',channels=['portal'],
            communication_consent=True,planned_appointments='Synthetic appointment',
            review_at=utcnow()+timedelta(days=10),response_steps='Synthetic agreed steps',urgent_help='Synthetic instructions',
            monitoring_hours='Synthetic review hours',rules={k:60 for k in KINDS},
            clinical_definitions='Synthetic practice definition',agreed_at=utcnow()))
        db.session.add(ClinicalRecord(institution_id=a.id,patient_id=p.id,author_id=users['dr'].id,
            kind='diagnoses',content='SYNTHETIC PG CLINICAL MARKER'))
        db.session.commit()
        ids={'patient':p.id,'peer':peer.id,'foreign':foreign.id,'same_dr':same_dr.id}
        logins={role:user.get_id() for role,user in users.items()}
        db.session.remove()
    yield app,ids,logins
    with app.app_context():db.session.remove();db.engine.dispose()


def client_for(case,role):
    client=case[0].test_client()
    with client.session_transaction() as session:
        session['_user_id']=case[2][role];session['_fresh']=True
        import time
        session['_auth_started_at']=session['_auth_last_seen']=int(time.time())
    return client


def simultaneous(call):
    barrier=threading.Barrier(2)
    def runner(index):
        barrier.wait(timeout=10)
        return call(index)
    with ThreadPoolExecutor(max_workers=2) as executor:
        return list(executor.map(runner,range(2)))


def test_simultaneous_check_ins_deduplicate_and_preserve_both_reports(pg_case):
    app,ids,_=pg_case
    results=simultaneous(lambda i:client_for(pg_case,'patient').post('/med/check-in',data=dict(
        patient_id=ids['patient'],kind='check_in',reason=f'Synthetic report {i}',monitoring_understood='on')).status_code)
    assert results==[302,302]
    with app.app_context():
        rows=list(db.session.scalars(select(ContinuityEvent)))
        assert len(rows)==1 and rows[0].category=='patient_reported'
        history=list(db.session.scalars(select(ContinuityHistory).where(ContinuityHistory.action=='submission')))
        assert len(history)==1 and history[0].detail!=rows[0].reason
        assert db.session.scalar(select(func.count(ClinicalRecord.id)))==1


def test_simultaneous_same_doctor_bookings_do_not_double_book(pg_case):
    from datetime import timezone
    app,ids,_=pg_case
    from test_calendar import approved,utc_on,time
    with app.app_context():
        _,day=approved(db.session.get(Patient,ids['patient']))
        when=utc_on(day,time(8))
    local=when.replace(tzinfo=timezone.utc).astimezone(TZ).isoformat(timespec='minutes')
    responses=simultaneous(lambda i:client_for(pg_case,'dr').post('/med/appointments',data=dict(
        patient_id=ids['patient' if i==0 else 'same_dr'],starts_at=local,service='General consultation')).status_code)
    assert responses==[302,302]
    with app.app_context():assert db.session.scalar(select(func.count(Appointment.id)))==1


def test_simultaneous_proposal_acceptance_is_idempotent_and_preserves_invoice(pg_case):
    from test_calendar import approved,utc_on,time,local
    from models import AppointmentProposal,CalendarHistory
    from sqlalchemy import text
    app,ids,_=pg_case
    with app.app_context():
        p=db.session.get(Patient,ids['patient']);_,day=approved(p)
        a=Appointment(patient_id=p.id,doctor_id=p.doctor_id,starts_at=utc_on(day,time(8)),
            ends_at=utc_on(day,time(8,30)),service='General consultation',status='scheduled',care_type='outpatient',visit_kind='followup')
        db.session.add(a);db.session.commit();identity=a.id
        db.session.execute(text('CREATE TABLE synthetic_invoice_links (id int PRIMARY KEY, appointment_id int REFERENCES appointments(id), paid_cents int)'))
        db.session.execute(text('INSERT INTO synthetic_invoice_links VALUES (1,:a,12345)'),{'a':identity});db.session.commit()
    assert client_for(pg_case,'dr_assist').post(f'/med/calendar/{identity}/propose',data={
        'version':1,'starts_at':local(utc_on(day,time(9,10))),'reason':'Agreed synthetic change'}).status_code==302
    with app.app_context():
        key=db.session.scalar(select(AppointmentProposal.token_digest))
    results=simultaneous(lambda i:client_for(pg_case,'patient').post(f'/med/calendar/proposals/{key}/respond',data={'decision':'accepted'}).status_code)
    assert sorted(results)==[200,409]
    with app.app_context():
        assert db.session.get(Appointment,identity).schedule_version==2
        assert db.session.scalar(select(func.count(CalendarHistory.id)).where(CalendarHistory.action=='proposal_accepted'))==1
        assert db.session.execute(text('SELECT appointment_id,paid_cents FROM synthetic_invoice_links')).one()==(identity,12345)


def test_simultaneous_overlapping_changes_respect_daily_capacity(pg_case):
    from test_calendar import approved,utc_on,time,local
    app,ids,_=pg_case
    with app.app_context():
        p=db.session.get(Patient,ids['patient']);policy,day=approved(p);policy.daily_limit=1
        appointments=[]
        for patient_id,hour in [(ids['patient'],8),(ids['same_dr'],10)]:
            a=Appointment(patient_id=patient_id,doctor_id=p.doctor_id,starts_at=utc_on(day+timedelta(days=7),time(hour)),
                service='General consultation',status='scheduled',care_type='outpatient',visit_kind='followup')
            db.session.add(a);db.session.flush();appointments.append(a.id)
        db.session.commit()
    results=simultaneous(lambda i:client_for(pg_case,'dr_assist').post(f'/med/appointments/{appointments[i]}/reschedule',data={
        'version':1,'confirmed':'yes','reason':'Agreed synthetic change',
        'starts_at':local(utc_on(day,time(8 if i==0 else 9,0 if i==0 else 10)))}).status_code)
    assert results==[302,302]
    with app.app_context():
        assert sum(db.session.get(Appointment,a).schedule_version==2 for a in appointments)==1


def test_simultaneous_different_start_overlaps_are_rechecked(pg_case):
    from test_calendar import approved,utc_on,time,local
    app,ids,_=pg_case
    with app.app_context():
        p=db.session.get(Patient,ids['patient']);_,day=approved(p)
        identities=[]
        for index,patient_id in enumerate([ids['patient'],ids['same_dr']]):
            a=Appointment(patient_id=patient_id,doctor_id=p.doctor_id,starts_at=utc_on(day+timedelta(days=7),time(8+index*2)),
                service='General consultation',status='scheduled',care_type='outpatient',visit_kind='first' if index==0 else 'followup')
            db.session.add(a);db.session.flush();identities.append(a.id)
        db.session.commit()
    results=simultaneous(lambda i:client_for(pg_case,'dr_assist').post(f'/med/appointments/{identities[i]}/reschedule',data={
        'version':1,'confirmed':'yes','reason':'Agreed synthetic change',
        'starts_at':local(utc_on(day,time(8,0 if i==0 else 35)))}).status_code)
    assert results==[302,302]
    with app.app_context():
        assert sum(db.session.get(Appointment,a).schedule_version==2 for a in identities)==1


def test_simultaneous_acknowledgment_has_one_state_transition(pg_case):
    app,ids,_=pg_case
    client_for(pg_case,'dr').post('/med/continuity/events',data=dict(patient_id=ids['patient'],
        kind='relapse',reason='Synthetic clinician event',definition_confirmed='on'))
    with app.app_context():identity=db.session.scalar(select(ContinuityEvent.id))
    results=simultaneous(lambda i:client_for(pg_case,'dr').post(f'/med/continuity/{identity}',
        data=dict(action='acknowledge',detail='Synthetic acknowledgment')).status_code)
    assert sorted(results)==[302,400]
    with app.app_context():
        assert db.session.scalar(select(func.count(ContinuityHistory.id)).where(ContinuityHistory.action=='acknowledge'))==1


@pytest.mark.parametrize('role',('dr','dr2','nurse','dr_assist','admin','patient','foreign'))
def test_postgres_role_and_cross_institution_record_queries(pg_case,role):
    _,ids,_=pg_case;client=client_for(pg_case,role)
    response=client.get(f'/med/patients/{ids["patient"]}/records/diagnoses')
    assert response.status_code==(200 if role=='dr' else 403 if role in ('dr_assist','patient') else 404)
    if role!='dr':assert b'SYNTHETIC PG CLINICAL MARKER' not in response.data
    for identity in (ids['peer'],ids['foreign']):
        response=client.get(f'/med/patients/{identity}/records/diagnoses')
        assert b'SYNTHETIC PG CLINICAL MARKER' not in response.data
        own=(role=='dr2' and identity==ids['peer']) or (role=='foreign' and identity==ids['foreign'])
        assert response.status_code==(200 if own else 403 if role in ('dr_assist','patient') else 404)
    assert client.post('/med/exports',data={'resource':'diagnoses','patient_id':ids['patient']}).status_code==(
        200 if role=='dr' else 403 if role in ('nurse','dr_assist','patient') else 404)


def test_diagnosis_join_negative_control_for_synthetic_financial_totals(isolated_database):
    # SQL oracle only. The checkout has no financial reporting implementation to validate.
    with psycopg.connect(isolated_database,autocommit=True) as c:
        c.execute('CREATE TABLE qa_diagnosis(patient_id int); CREATE TABLE qa_payment(patient_id int, amount numeric)')
        c.execute('INSERT INTO qa_diagnosis VALUES(1),(1),(1); INSERT INTO qa_payment VALUES(1,100),(1,50)')
        naive=c.execute('SELECT sum(amount) FROM qa_payment JOIN qa_diagnosis USING(patient_id)').fetchone()[0]
        safe=c.execute('SELECT sum(amount) FROM qa_payment WHERE EXISTS (SELECT 1 FROM qa_diagnosis WHERE qa_diagnosis.patient_id=qa_payment.patient_id)').fetchone()[0]
        assert naive==450 and safe==150


def test_forward_ramosolo_007_008_preserve_financial_provenance_and_guard_outbox(isolated_database):
    """Metadata-compatible v6 replay with synthetic sentinels, never live records."""
    with psycopg.connect(isolated_database,autocommit=True) as c:
        c.execute(migration(1).replace('lesonto','ramosolo'))
        c.execute('SET search_path TO ramosolo,public')
        c.execute('INSERT INTO schema_versions(version) VALUES (2),(3),(4),(5),(6)')
        c.execute('ALTER TABLE appointments ADD COLUMN institution_id integer NOT NULL')
        c.execute("INSERT INTO institutions(name,kind) VALUES ('Synthetic practice','medical')")
        c.execute("INSERT INTO users(name,email,password_hash,enabled,session_version,failed_logins) VALUES ('Synthetic clinician','qa@example.test','disabled-login',true,1,0)")
        c.execute("INSERT INTO memberships(user_id,institution_id,role,enabled) VALUES(1,1,'dr',true)")
        c.execute("INSERT INTO patients(institution_id,doctor_id,name) VALUES(1,1,'Synthetic patient')")
        c.execute("INSERT INTO appointments(patient_id,doctor_id,starts_at,status,service,institution_id) VALUES(1,1,timezone('UTC',now()),'scheduled','Synthetic service',1)")
        c.execute('''CREATE TABLE medical_invoices(id int PRIMARY KEY,total numeric,currency text);
          CREATE TABLE medical_payment_entries(id int PRIMARY KEY,invoice_id int,amount numeric);
          CREATE TABLE demo_datasets(id int PRIMARY KEY,manifest json);
          CREATE TABLE communication_preferences(id int PRIMARY KEY,institution_id int,patient_id int,
            in_app_enabled boolean,in_app_consent_at timestamp,version int,changed_by int,changed_at timestamp);
          CREATE TABLE notification_outbox(id int PRIMARY KEY,institution_id int,appointment_id int,
            channel text,state text CHECK(state IN ('pending','sent','failed','cancelled')),
            sent_at timestamp,invalidated_at timestamp,result_code text);
          CREATE TABLE attendance_followups(id int PRIMARY KEY,institution_id int,appointment_id int,
            rule text,state text,revision int,checked_at timestamp)''')
        c.execute("INSERT INTO medical_invoices VALUES(1,100,'ZAR'); INSERT INTO medical_payment_entries VALUES(1,1,40); INSERT INTO demo_datasets VALUES(1,'{\"synthetic\":true}')")
        c.execute("INSERT INTO communication_preferences VALUES(1,1,1,true,timezone('UTC',now()),1,NULL,timezone('UTC',now()))")
        c.execute("INSERT INTO notification_outbox VALUES(1,1,1,'in_app','pending',NULL,NULL,''),(2,1,1,'in_app','sent',timezone('UTC',now()),NULL,'')")
        before={name:c.execute(f'SELECT to_jsonb(t) FROM {name} t').fetchall() for name in ('medical_invoices','medical_payment_entries','demo_datasets','appointments')}
        c.execute(migration(7));c.execute(migration(8));c.execute(migration(9))
        for name,rows in before.items():
            after=c.execute(f'SELECT to_jsonb(t) FROM {name} t').fetchall()
            assert len(rows)==len(after)
            for (old,),(new,) in zip(rows,after):assert all(new[k]==v for k,v in old.items())
        assert c.execute('SELECT max(version) FROM schema_versions').fetchone()[0]==9
        assert not c.execute("SELECT has_table_privilege('anon','ramosolo.referral_clinical_records','SELECT')").fetchone()[0]
        c.execute("""INSERT INTO communication_decisions(institution_id,patient_id,purpose,channel,scope,status,
            destination,timezone,method,notice_version,recorded_by_id,recorded_at)
            VALUES(1,1,'reminders','portal','practice','withdrawn','','Africa/Johannesburg','synthetic','synthetic-v1',1,timezone('UTC',now()))""")
        assert c.execute('SELECT state FROM notification_outbox ORDER BY id').fetchall()==[('cancelled',),('sent',)]
        assert not c.execute('SELECT in_app_enabled FROM communication_preferences').fetchone()[0]
        c.execute("UPDATE notification_outbox SET state='pending' WHERE id=1")
        assert c.execute('SELECT state FROM notification_outbox WHERE id=1').fetchone()[0]=='cancelled'
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("UPDATE notification_outbox SET state='sent',sent_at=timezone('UTC',now()) WHERE id=1")
        assert c.execute('SELECT state FROM notification_outbox WHERE id=1').fetchone()[0]=='cancelled'


def test_simultaneous_referral_creation_and_state_update(pg_case):
    app,ids,logins=pg_case
    from models import Referral
    from datetime import timezone
    referred=(utcnow()-timedelta(days=1)).replace(tzinfo=timezone.utc).astimezone(TZ).isoformat(timespec='minutes')
    data=dict(patient_id=ids['patient'],direction='incoming',other_party='Synthetic service',
        referred_at=referred,requested_action='Arrange contact',owner_id=int(logins['dr'].split(':')[0]),submission_key=uuid.uuid4().hex)
    assert simultaneous(lambda i:client_for(pg_case,'dr').post('/med/referrals',data=data).status_code)==[302,302]
    with app.app_context():
        assert db.session.scalar(select(func.count(Referral.id)))==1
        identity=db.session.scalar(select(Referral.id))
    replies=simultaneous(lambda i:client_for(pg_case,'dr').post(f'/med/referrals/{identity}',data=dict(
        version=1,action='transition',status='acknowledged',response_at=referred)).status_code)
    assert sorted(replies)==[302,409]
    with app.app_context():assert db.session.scalar(select(Referral.version))==2


def test_simultaneous_review_signoff_preserves_one_signed_review_and_next_task(pg_case):
    app,ids,_=pg_case
    from models import CareReview, CareReviewSignoff
    from coordination_services import ensure_review
    from flask import g
    from datetime import timezone
    with app.app_context():
        g.membership=db.session.scalar(select(Membership).where(Membership.role=='dr',Membership.user_id==1))
        # Service history uses the authenticated actor; initialize through the normal route instead.
        plan_id=db.session.scalar(select(CarePlan.id))
    assigned=client_for(pg_case,'dr').post(f'/med/care-plans/{plan_id}/review',data=dict(
        version=1,action='assign',owner_id=1,due_at=(utcnow()+timedelta(days=1)).replace(tzinfo=timezone.utc).astimezone(TZ).isoformat(timespec='minutes')))
    assert assigned.status_code==302
    with app.app_context():
        row=db.session.scalar(select(CareReview));identity=row.id;version=row.version
    data=dict(version=version,review_id=identity,action='complete',outcome='Synthetic signed review',
        reviewed_at=(utcnow()-timedelta(minutes=1)).replace(tzinfo=timezone.utc).astimezone(TZ).isoformat(timespec='minutes'),
        next_review_at=(utcnow()+timedelta(days=7)).replace(tzinfo=timezone.utc).astimezone(TZ).isoformat(timespec='minutes'))
    results=simultaneous(lambda i:client_for(pg_case,'dr').post(f'/med/care-plans/{plan_id}/review',data=data).status_code)
    assert sorted(results)==[302,409]
    with app.app_context():
        assert db.session.scalar(select(func.count(CareReviewSignoff.id)))==1
        assert db.session.scalar(select(func.count(CareReview.id)).where(CareReview.status=='pending'))==1


def test_simultaneous_discharge_recording_creates_one_episode_followup(pg_case):
    app,ids,_=pg_case
    from models import Admission, DischargeFollowup
    with app.app_context():
        row=Admission(patient_id=ids['patient'],facility='Synthetic facility',admitted_at=utcnow()-timedelta(days=1))
        db.session.add(row);db.session.commit();identity=row.id
    results=simultaneous(lambda i:client_for(pg_case,'dr').post(f'/med/admissions/{identity}/discharge').status_code)
    assert results==[302,302]
    with app.app_context():assert db.session.scalar(select(func.count(DischargeFollowup.id)))==1
