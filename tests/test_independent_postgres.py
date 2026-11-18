"""Real local PostgreSQL tests. Never accepts a live URL or imports credentials."""
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
import json
import pytest
import psycopg
from psycopg import sql
from sqlalchemy import select, func, create_engine, inspect, text
from app import create_app
from extensions import db
from models import (User, Institution, Membership, Patient, CareAssignment, CarePlan,
                    Appointment, ContinuityEvent, ContinuityHistory, ClinicalRecord)
from medical_services import utcnow, TZ
from continuity_services import KINDS

ROOT=Path(__file__).resolve().parents[1]
BIN=Path(os.environ.get('RAMOSOLO_POSTGRES_BIN', 'C:/Program Files/PostgreSQL/18/bin'))


def test_factory_cli_schema_after_rollback_and_connection_reuse(isolated_database):
    from flask import has_app_context
    assert not has_app_context()
    with psycopg.connect(isolated_database, autocommit=True) as connection:
        connection.execute('CREATE SCHEMA ramosolo')
    app = create_app({'TESTING': True, 'SECRET_KEY': 'synthetic-startup',
        'SQLALCHEMY_DATABASE_URI': isolated_database.replace('postgresql://', 'postgresql+psycopg://', 1),
        'SQLALCHEMY_ENGINE_OPTIONS': {'pool_size': 1, 'max_overflow': 0},
        'DB_SCHEMA': 'ramosolo'})
    assert not has_app_context()
    try:
        with app.app_context():
            engine = db.engine
            db.create_all()  # Only the isolated synthetic database.
            with engine.connect() as connection:
                physical = connection.connection.driver_connection
                assert connection.scalar(text('SELECT current_schema()')) == 'ramosolo'
                connection.rollback()
            with engine.connect() as connection:
                assert connection.connection.driver_connection is physical
                assert connection.scalar(text('SELECT current_schema()')) == 'ramosolo'
                # Commit a different session setting to prove checkout restores it.
                connection.execute(text('SET SESSION search_path TO public'))
                connection.commit()
        for _ in range(2):
            result = app.test_cli_runner().invoke(args=['check-connections', '--only', 'database'])
            assert result.exit_code == 0, result.output
            assert 'schema ramosolo. No records changed.' in result.output
            assert not has_app_context()
        with app.app_context():
            with engine.connect() as connection:
                assert connection.connection.driver_connection is physical
                assert connection.scalar(text('SELECT current_schema()')) == 'ramosolo'
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()


def test_reconciliation_draft_aborts_atomically_on_incompatible_catalog(isolated_database):
    """The new production draft must refuse an incomplete synthetic baseline."""
    from psycopg.errors import RaiseException
    draft=(ROOT/'migrations'/'010_ramosolo_live_reconciliation_draft.sql').read_text(encoding='utf-8')
    with psycopg.connect(isolated_database,autocommit=True) as connection:
        connection.execute('CREATE SCHEMA ramosolo')
        connection.execute('CREATE TABLE ramosolo.schema_versions(version integer PRIMARY KEY)')
        connection.execute('INSERT INTO ramosolo.schema_versions VALUES (1),(2),(3),(4),(5),(6)')
        with pytest.raises(RaiseException):
            connection.execute(draft)
        connection.rollback()
        assert connection.execute('SELECT version FROM ramosolo.schema_versions ORDER BY version').fetchall()==[(1,),(2,),(3,),(4,),(5,),(6,)]
        assert connection.execute("SELECT to_regclass('ramosolo.care_plans')").fetchone()[0] is None
        assert connection.execute("SELECT to_regclass('ramosolo.appointment_proposals')").fetchone()[0] is None


def test_reconciliation_draft_applies_to_reconstructed_production_fixture(isolated_database):
    """Apply the actual checked-in draft to a metadata-reconstructed clone."""
    fixture = (ROOT/'tests'/'fixtures'/'ramosolo_live_fixture.sql').read_text(encoding='utf-8')
    draft = (ROOT/'migrations'/'010_ramosolo_live_reconciliation_draft.sql').read_text(encoding='utf-8')
    snapshot = json.loads((ROOT/'tests'/'fixtures'/'ramosolo_live_catalog.json').read_text(encoding='utf-8'))['snapshot']
    ledger_write = "INSERT INTO ramosolo.schema_versions(version) VALUES (7),(8),(9);"
    assert draft.count(ledger_write) == 1
    ledger_position = draft.index(ledger_write)
    for required_postcondition in (
        'Target table postcondition failed', 'ORM column postcondition failed',
        'Trigger inventory postcondition failed', 'Coordination trigger postcondition failed',
        'Target table or sequence owner postcondition failed',
        'Coordination routine grants postcondition failed',
        'Existing trigger changed during reconciliation: appointments.appointment_capacity_guard',
    ):
        assert draft.index(required_postcondition) < ledger_position
    with psycopg.connect(isolated_database, autocommit=True) as connection:
        connection.execute(fixture)
        assert connection.execute('SELECT count(*) FROM ramosolo.schema_versions').fetchone()[0] == 6
        assert connection.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND c.relkind='r'").fetchone()[0] == len(snapshot['tables'])
        assert connection.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='ramosolo'").fetchone()[0] == len(snapshot['columns'])
        assert connection.execute("SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='ramosolo' AND c.contype <> 'n'").fetchone()[0] == len(snapshot['constraints'])
        assert connection.execute("SELECT count(*) FROM pg_indexes WHERE schemaname='ramosolo'").fetchone()[0] == len(snapshot['indexes'])
        assert connection.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND c.relkind='S'").fetchone()[0] == len(snapshot['sequences'])
        assert connection.execute("SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND NOT t.tgisinternal").fetchone()[0] == len(snapshot['triggers'])
        assert connection.execute("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='ramosolo'").fetchone()[0] == len(snapshot['functions'])
        # pg_get_* definitions include schema qualification only when ramosolo is outside search_path.
        connection.execute('SET search_path TO public')
        actual_columns = connection.execute("SELECT t.relname,a.attnum::text,a.attname,format_type(a.atttypid,a.atttypmod),coalesce(pg_get_expr(d.adbin,d.adrelid),''),coalesce(a.attidentity::text,''),coalesce(a.attgenerated::text,''),a.attnotnull::text FROM pg_attribute a JOIN pg_class t ON t.oid=a.attrelid JOIN pg_namespace n ON n.oid=t.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE n.nspname='ramosolo' AND t.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped ORDER BY t.relname,a.attnum").fetchall()
        expected_columns = [(c['table'],str(c['position']),c['name'],c['type'],c['default'] or '',c['identity'] or '',c['generated'] or '',str(bool(c['not_null'])).lower()) for c in sorted(snapshot['columns'],key=lambda c:(c['table'],c['position']))]
        if actual_columns != expected_columns:
            print('Fixture column signature mismatches:',[(expected,actual) for expected,actual in zip(expected_columns,actual_columns) if expected!=actual][:20])
        assert actual_columns == expected_columns
        actual_functions = dict(connection.execute("SELECT p.proname,md5(p.prosrc) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='ramosolo'").fetchall())
        assert actual_functions == {row['name']:row['source_md5'] for row in snapshot['functions']}
        actual_function_security = {name: (owner, config, security_definer, acl)
            for name, owner, config, security_definer, acl in connection.execute("""
                SELECT p.proname,pg_get_userbyid(p.proowner),p.proconfig,p.prosecdef,p.proacl::text
                FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='ramosolo'
            """).fetchall()}
        assert actual_function_security == {row['name']: (row['owner'], row['config'],
            row['security_definer'], row['acl']) for row in snapshot['functions']}
        actual_triggers = {(table,name):definition for table,name,definition in connection.execute("SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND NOT t.tgisinternal").fetchall()}
        assert actual_triggers == {(row['table'],row['name']):row['definition'] for row in snapshot['triggers']}
        actual_trigger_states = {(table,name):state for table,name,state in connection.execute("SELECT c.relname,t.tgname,t.tgenabled::text FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND NOT t.tgisinternal").fetchall()}
        assert actual_trigger_states == {(row['table'],row['name']):row['enabled'] for row in snapshot['triggers']}
        actual_constraints = {(table,name):(kind,deferrable,deferred,validated) for table,name,kind,deferrable,deferred,validated in connection.execute("SELECT t.relname,c.conname,c.contype::text,c.condeferrable,c.condeferred,c.convalidated FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='ramosolo' AND c.contype <> 'n'").fetchall()}
        assert actual_constraints == {(row['table'],row['name']):(row['type'],row['deferrable'],row['initially_deferred'],row['validated']) for row in snapshot['constraints']}
        production_constraints = {(row['table'],row['name']):row['definition'] for row in snapshot['constraints']}
        for key in (('appointments','appointment_identity'),('appointments','appointment_interval')):
            actual = connection.execute("SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid WHERE t.relname=%s AND c.conname=%s",key).fetchone()[0]
            assert actual == production_constraints[key]
        actual_indexes = dict(connection.execute("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='ramosolo'").fetchall())
        assert actual_indexes == {row['name']:row['definition'] for row in snapshot['indexes']}
        actual_tables = {name: (owner, rls, force_rls, acl) for name,owner,rls,force_rls,acl in connection.execute("""
            SELECT c.relname,pg_get_userbyid(c.relowner),c.relrowsecurity,c.relforcerowsecurity,c.relacl::text
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='ramosolo' AND c.relkind='r'
        """).fetchall()}
        expected_table_grants = {row['table']: row for row in snapshot['table_grants']}
        assert actual_tables == {row['name']:(row['owner'],row['rls'],row['force_rls'],expected_table_grants[row['name']]['acl'])
            for row in snapshot['tables']}
        actual_sequences = {name:(owner,seqtype,increment,minimum,maximum,start,cache,cycle,acl)
            for name,owner,seqtype,increment,minimum,maximum,start,cache,cycle,acl in connection.execute("""
                SELECT c.relname,pg_get_userbyid(c.relowner),format_type(s.seqtypid,NULL),s.seqincrement,s.seqmin,s.seqmax,
                    s.seqstart,s.seqcache,s.seqcycle,c.relacl::text
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_sequence s ON s.seqrelid=c.oid
                WHERE n.nspname='ramosolo'
            """).fetchall()}
        assert actual_sequences == {row['name']:(row['owner'],row['type'],row['increment'],row['min'],row['max'],
            row['start'],row['cache'],row['cycle'],row['acl']) for row in snapshot['sequences']}
        schema_owner, schema_acl = connection.execute("SELECT pg_get_userbyid(nspowner),nspacl::text FROM pg_namespace WHERE nspname='ramosolo'").fetchone()
        assert (schema_owner, schema_acl) == ('postgres', '{postgres=UC/postgres}')
        assert connection.execute("SELECT count(*) FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace WHERE d.defaclrole='postgres'::regrole AND (d.defaclnamespace=0 OR n.nspname='ramosolo')").fetchone()[0] == 0
        before = connection.execute("SELECT to_jsonb(a) FROM ramosolo.appointments a WHERE id=1").fetchone()[0]
        connection.execute('SET ROLE postgres')
        connection.execute(draft)
        connection.execute('RESET ROLE')
        assert connection.execute('SELECT version FROM ramosolo.schema_versions ORDER BY version').fetchall() == [(n,) for n in range(1, 10)]
        assert connection.execute("SELECT name FROM ramosolo.institutions ORDER BY id").fetchall() == [
            ('Synthetic fixture practice A',), ('Synthetic fixture practice B',)]
        after = connection.execute("SELECT to_jsonb(a) FROM ramosolo.appointments a WHERE id=1").fetchone()[0]
        assert after == before
        with pytest.raises(psycopg.errors.RaiseException):
            connection.execute(draft)
        connection.rollback()
        assert connection.execute('SELECT version FROM ramosolo.schema_versions ORDER BY version').fetchall() == [
            (n,) for n in range(1, 10)]
        orm_columns = {(table.name, column.name) for table in db.metadata.tables.values()
            for column in table.columns}
        fixture_columns = set(connection.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='ramosolo'").fetchall())
        assert orm_columns <= fixture_columns
        assert connection.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='ramosolo' AND table_type='BASE TABLE'").fetchone()[0] == 51
        assert connection.execute("SELECT to_jsonb(a) FROM ramosolo.appointments a WHERE id=1").fetchone()[0] == before


def _reconstructed_fixture_and_draft(connection):
    fixture = (ROOT/'tests'/'fixtures'/'ramosolo_live_fixture.sql').read_text(encoding='utf-8')
    draft = (ROOT/'migrations'/'010_ramosolo_live_reconciliation_draft.sql').read_text(encoding='utf-8')
    connection.execute(fixture)
    connection.execute('SET ROLE postgres')
    connection.execute(draft)
    connection.execute('RESET ROLE')


def test_constraint_fingerprint_is_order_stable_and_rejects_definition_drift(isolated_database):
    """Equivalent metadata order hashes identically; a changed check is rejected."""
    from psycopg.errors import RaiseException
    from verification.constraint_fingerprint import (
        constraint_fingerprint,
        sql_constraint_fingerprint_expression,
    )

    snapshot = json.loads(
        (ROOT/'tests'/'fixtures'/'ramosolo_live_catalog.json').read_text(encoding='utf-8')
    )['snapshot']
    fixture_profile = json.loads(
        (ROOT/'tests'/'fixtures'/'ramosolo_pg17_fixture_profile.json').read_text(encoding='utf-8')
    )
    constraints = snapshot['constraints']
    expected = constraint_fingerprint(constraints)
    assert constraint_fingerprint(list(reversed(constraints))) == expected

    fixture = (ROOT/'tests'/'fixtures'/'ramosolo_live_fixture.sql').read_text(encoding='utf-8')
    draft = (ROOT/'migrations'/'010_ramosolo_live_reconciliation_draft.sql').read_text(encoding='utf-8')
    with psycopg.connect(isolated_database, autocommit=True) as connection:
        connection.execute(fixture)
        connection.execute('SET search_path TO public')
        actual = connection.execute(
            f'SELECT {sql_constraint_fingerprint_expression()}'
        ).fetchone()[0]
        actual_rows = connection.execute('''
            SELECT t.relname,c.conname,c.contype::text,pg_get_constraintdef(c.oid),
                   c.condeferrable,c.condeferred,c.convalidated
            FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
            JOIN pg_namespace n ON n.oid=t.relnamespace
            WHERE n.nspname='ramosolo' AND c.contype <> 'n'
        ''').fetchall()
        expected_rows = {
            (row['table'],row['name']):(
                row['type'],row['definition'],row['deferrable'],
                row['initially_deferred'],row['validated'],
            ) for row in constraints
        }
        actual_map = {(table,name):(kind,definition,deferrable,deferred,validated)
            for table,name,kind,definition,deferrable,deferred,validated in actual_rows}
        assert set(actual_map) == set(expected_rows)
        fixture_constraint_rows = [
            {
                'table':table,'name':name,'type':kind,'definition':definition,
                'deferrable':deferrable,'initially_deferred':deferred,'validated':validated,
            }
            for table,name,kind,definition,deferrable,deferred,validated in actual_rows
        ]
        definition_differences = [
            (key, expected_rows[key], actual_map.get(key))
            for key in expected_rows if expected_rows[key] != actual_map.get(key)
        ]
        assert len(definition_differences) == fixture_profile['definition_render_differences']
        assert all(
            expected_rows[key][0] == actual_map[key][0]
            and expected_rows[key][2:] == actual_map[key][2:]
            for key, _, _ in definition_differences
        )
        fixture_fingerprint = constraint_fingerprint(fixture_constraint_rows)
        assert actual == fixture_fingerprint == fixture_profile['constraint_fingerprint']
        assert fixture_fingerprint != expected

        connection.execute('''
            ALTER TABLE ramosolo.appointments DROP CONSTRAINT appointments_status_check;
            ALTER TABLE ramosolo.appointments
              ADD CONSTRAINT appointments_status_check CHECK (status <> 'synthetic_drift');
        ''')
        connection.execute('SET ROLE postgres')
        with pytest.raises(RaiseException, match='Existing constraint definition drift'):
            connection.execute(draft)
        connection.rollback()
        connection.execute('RESET ROLE')
        assert connection.execute(
            'SELECT version FROM ramosolo.schema_versions ORDER BY version'
        ).fetchall() == [(n,) for n in range(1, 7)]
        assert connection.execute(
            "SELECT to_regclass('ramosolo.care_plans')"
        ).fetchone()[0] is None
        assert connection.execute(
            "SELECT to_regclass('ramosolo.appointment_proposals')"
        ).fetchone()[0] is None


def test_reconciliation_draft_rejects_observed_schema_drift_atomically(isolated_database):
    """A full fixture with an unexpected definition must not get partial DDL."""
    from psycopg.errors import RaiseException
    fixture = (ROOT/'tests'/'fixtures'/'ramosolo_live_fixture.sql').read_text(encoding='utf-8')
    draft = (ROOT/'migrations'/'010_ramosolo_live_reconciliation_draft.sql').read_text(encoding='utf-8')
    with psycopg.connect(isolated_database, autocommit=True) as connection:
        connection.execute(fixture)
        connection.execute("ALTER TABLE ramosolo.appointments ALTER COLUMN schedule_version SET DEFAULT 2")
        sentinel = connection.execute("SELECT to_jsonb(a) FROM ramosolo.appointments a WHERE id=1").fetchone()[0]
        connection.execute('SET ROLE postgres')
        with pytest.raises(RaiseException, match='Existing column definition drift'):
            connection.execute(draft)
        connection.rollback()
        connection.execute('RESET ROLE')
        assert connection.execute('SELECT version FROM ramosolo.schema_versions ORDER BY version').fetchall() == [
            (n,) for n in range(1, 7)]
        assert connection.execute("SELECT to_regclass('ramosolo.care_plans')").fetchone()[0] is None
        assert connection.execute("SELECT to_regclass('ramosolo.appointment_proposals')").fetchone()[0] is None
        assert connection.execute("SELECT to_jsonb(a) FROM ramosolo.appointments a WHERE id=1").fetchone()[0] == sentinel
        assert connection.execute("SELECT column_default FROM information_schema.columns WHERE table_schema='ramosolo' AND table_name='appointments' AND column_name='schedule_version'").fetchone()[0] == '2'


def test_reconciliation_draft_rolls_back_after_midflight_failure(isolated_database):
    """A post-apply DDL failure rolls back earlier objects and ledger writes."""
    from psycopg.errors import RaiseException
    fixture = (ROOT/'tests'/'fixtures'/'ramosolo_live_fixture.sql').read_text(encoding='utf-8')
    draft = (ROOT/'migrations'/'010_ramosolo_live_reconciliation_draft.sql').read_text(encoding='utf-8')
    with psycopg.connect(isolated_database, autocommit=True) as connection:
        connection.execute(fixture)
        connection.execute('''
            CREATE FUNCTION public.abort_after_synthetic_care_plans() RETURNS event_trigger
            LANGUAGE plpgsql AS $$
            BEGIN
              IF EXISTS (SELECT 1 FROM pg_event_trigger_ddl_commands()
                         WHERE command_tag='CREATE TABLE' AND object_identity='ramosolo.care_plans') THEN
                RAISE EXCEPTION 'synthetic mid-migration fault';
              END IF;
            END $$;
            CREATE EVENT TRIGGER synthetic_reconciliation_fault ON ddl_command_end
              EXECUTE FUNCTION public.abort_after_synthetic_care_plans();
        ''')
        sentinel = connection.execute("SELECT to_jsonb(a) FROM ramosolo.appointments a WHERE id=1").fetchone()[0]
        connection.execute('SET ROLE postgres')
        with pytest.raises(RaiseException, match='synthetic mid-migration fault'):
            connection.execute(draft)
        connection.rollback()
        connection.execute('RESET ROLE')
        assert connection.execute('SELECT version FROM ramosolo.schema_versions ORDER BY version').fetchall() == [
            (n,) for n in range(1, 7)]
        assert connection.execute("SELECT to_regclass('ramosolo.care_plans')").fetchone()[0] is None
        assert connection.execute("SELECT to_regclass('ramosolo.appointment_proposals')").fetchone()[0] is None
        assert connection.execute("SELECT to_jsonb(a) FROM ramosolo.appointments a WHERE id=1").fetchone()[0] == sentinel


def test_reconciliation_draft_rolls_back_when_postcondition_fails(isolated_database):
    """A failed final safeguard check cannot leave objects or ledger entries."""
    from psycopg.errors import RaiseException
    fixture = (ROOT/'tests'/'fixtures'/'ramosolo_live_fixture.sql').read_text(encoding='utf-8')
    draft = (ROOT/'migrations'/'010_ramosolo_live_reconciliation_draft.sql').read_text(encoding='utf-8')
    with psycopg.connect(isolated_database, autocommit=True) as connection:
        connection.execute(fixture)
        connection.execute('''
            CREATE FUNCTION public.disable_first_reconciliation_trigger() RETURNS event_trigger
            LANGUAGE plpgsql AS $$
            BEGIN
              IF TG_TAG='CREATE TRIGGER' THEN
                ALTER TABLE ramosolo.notification_outbox DISABLE TRIGGER coordination_outbox_permission_guard;
              END IF;
            END $$;
            CREATE EVENT TRIGGER synthetic_postcondition_fault ON ddl_command_end
              EXECUTE FUNCTION public.disable_first_reconciliation_trigger();
        ''')
        connection.execute('SET ROLE postgres')
        with pytest.raises(RaiseException, match='Coordination trigger postcondition failed'):
            connection.execute(draft)
        connection.rollback()
        connection.execute('RESET ROLE')
        assert connection.execute('SELECT version FROM ramosolo.schema_versions ORDER BY version').fetchall() == [
            (n,) for n in range(1, 7)]
        assert connection.execute("SELECT to_regclass('ramosolo.care_plans')").fetchone()[0] is None
        assert connection.execute("SELECT to_regclass('ramosolo.appointment_proposals')").fetchone()[0] is None
        assert connection.execute("SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND NOT t.tgisinternal").fetchone()[0] == 32


def test_reconciliation_migrated_fixture_supports_app_writes_and_boundaries(isolated_database):
    """Exercise the actual SQL draft through Flask against the reconstructed live schema."""
    from datetime import time, timezone
    from sqlalchemy import func
    from models import AvailabilityPolicy, AvailabilitySession, AppointmentProposal, CalendarHistory
    from medical_services import utcnow
    from scheduling_services import local_day
    from test_calendar import local, utc_on
    fixture = (ROOT/'tests'/'fixtures'/'ramosolo_live_fixture.sql').read_text(encoding='utf-8')
    draft = (ROOT/'migrations'/'010_ramosolo_live_reconciliation_draft.sql').read_text(encoding='utf-8')
    with psycopg.connect(isolated_database, autocommit=True) as connection:
        connection.execute(fixture)
        connection.execute('SET ROLE postgres')
        connection.execute(draft)
        connection.execute('RESET ROLE')

    app = create_app({'TESTING': True, 'SECRET_KEY': 'synthetic-reconciliation-app',
        'SQLALCHEMY_DATABASE_URI': isolated_database.replace('postgresql://','postgresql+psycopg://',1),
        'SQLALCHEMY_ENGINE_OPTIONS': {}, 'DB_SCHEMA': 'ramosolo', 'WTF_CSRF_ENABLED': False})
    synthetic_password = 'Synthetic-only reconciliation login 3!'
    with app.app_context():
        doctor = db.session.get(User, 1)
        doctor.set_password(synthetic_password)
        admin = User(name='Synthetic fixture admin', email='fixture-admin@example.test',
            password_hash='disabled-synthetic-login', enabled=True, session_version=1)
        second_portal_user = User(name='Synthetic fixture patient B', email='fixture-patient-b@example.test',
            password_hash='disabled-synthetic-login', enabled=True, session_version=1)
        db.session.add_all([admin, second_portal_user])
        db.session.flush()
        db.session.add(Membership(user_id=admin.id, institution_id=1, role='admin', enabled=True))
        db.session.add(Membership(user_id=second_portal_user.id, institution_id=1, role='patient', enabled=True))
        db.session.flush()
        second_patient = Patient(institution_id=1, user_id=second_portal_user.id, doctor_id=1,
            name='Synthetic fixture patient D')
        db.session.add(second_patient)
        db.session.commit()
        second_patient_id = second_patient.id

        # Explicit synthetic in-app consent and an institution-approved policy
        # let the application create a real pending job; no external channel is enabled.
        timestamp = utcnow()
        policy_id = db.session.execute(text('''INSERT INTO ramosolo.reminder_policies
            (institution_id,enabled,version,max_attempts,retry_seconds,link_minutes,catchup_minutes,updated_by,updated_at)
            VALUES (1,true,1,3,60,1440,60,:admin,:now) RETURNING id'''),
            {'admin': admin.id, 'now': timestamp}).scalar_one()
        db.session.execute(text('INSERT INTO ramosolo.reminder_leads(policy_id,minutes) VALUES (:id,60)'), {'id': policy_id})
        db.session.execute(text('''INSERT INTO ramosolo.communication_preferences
            (institution_id,patient_id,in_app_enabled,in_app_consent_at,email_enabled,sms_enabled,version,
             guest_verified_digest,changed_by,changed_at)
            VALUES (1,1,true,:now,false,false,1,NULL,4,:now),
                   (1,:patient,true,:now,false,false,1,NULL,:user,:now)'''),
            {'now': timestamp, 'patient': second_patient.id, 'user': second_portal_user.id})
        db.session.commit()

        patient = db.session.get(Patient, 1)
        schedule_policy = AvailabilityPolicy(institution_id=1, doctor_id=1, daily_limit=2,
            enabled=True, holidays_confirmed=True, horizon_days=90, hold_minutes=10)
        db.session.add(schedule_policy)
        db.session.flush()
        db.session.add(AvailabilitySession(policy_id=schedule_policy.id, weekday=2,
            care_type='outpatient', opens_at=time(8), closes_at=time(17), duration_minutes=30,
            first_minutes=60, assessment_minutes=90, break_minutes=5))
        day = local_day(utcnow()) + timedelta(days=7)
        while day.weekday() != 2:
            day += timedelta(days=1)
        db.session.commit()

    client = app.test_client()
    response = client.post('/auth/login', data={
        'email': 'fixture-doctor-a@example.test', 'password': synthetic_password})
    assert response.status_code == 302 and '/med' in response.headers['Location']
    assert client.get('/med').status_code == 200
    assert client.get('/med/appointments').status_code == 200
    assert client.get('/med/calendar').status_code == 200

    first_start = utc_on(day, time(8))
    first_local = local(first_start)
    case = (app, {'patient': 1, 'second': second_patient_id}, {'dr': '1:2'})
    results = simultaneous(lambda i: client_for(case, 'dr').post('/med/appointments', data={
        'patient_id': case[1]['patient' if i == 0 else 'second'],
        'starts_at': first_local, 'service': 'General consultation',
        'care_type': 'outpatient', 'visit_kind': 'followup'}).status_code)
    assert results == [302, 302]
    with app.app_context():
        booked = list(db.session.scalars(select(Appointment).where(Appointment.starts_at == first_start,
            Appointment.status == 'scheduled')))
        assert len(booked) == 1
        first_appointment_id = booked[0].id
        assert (booked[0].institution_id, booked[0].doctor_id,
            booked[0].visit_kind, booked[0].schedule_version) == (1, 1, 'routine', 1)
        assert booked[0].patient_id in (1, second_patient_id)
        pending = db.session.execute(text('''SELECT count(*) FROM ramosolo.notification_outbox
            WHERE appointment_id=:id AND state='pending' AND appointment_version=1'''),
            {'id': first_appointment_id}).scalar_one()
        assert pending == 1

    # A caller bypassing Flask still cannot mark a job sent without a published notice.
    with psycopg.connect(isolated_database) as connection:
        with pytest.raises(psycopg.errors.RaiseException, match='A sent state requires actual in-app publication'):
            connection.execute("UPDATE ramosolo.notification_outbox SET state='sent',sent_at=timezone('UTC',now()),attempt_count=1 WHERE appointment_id=%s AND appointment_version=1", (first_appointment_id,))
        connection.rollback()
        assert connection.execute("SELECT state FROM ramosolo.notification_outbox WHERE appointment_id=%s AND appointment_version=1", (first_appointment_id,)).fetchone()[0] == 'pending'

    # A second distinct slot reaches the configured daily cap; a third write is refused.
    second_start = utc_on(day, time(8, 35))
    assert client.post('/med/appointments', data={'patient_id': second_patient_id,
        'starts_at': local(second_start), 'service': 'General consultation',
        'care_type': 'outpatient', 'visit_kind': 'followup'}).status_code == 302
    third_start = utc_on(day, time(9, 10))
    assert client.post('/med/appointments', data={'patient_id': 1,
        'starts_at': local(third_start), 'service': 'General consultation',
        'care_type': 'outpatient', 'visit_kind': 'followup'}).status_code == 302
    with app.app_context():
        assert db.session.scalar(select(func.count(Appointment.id)).where(Appointment.starts_at.in_((first_start, second_start)))) == 2
        assert db.session.scalar(select(func.count(Appointment.id)).where(Appointment.starts_at == third_start)) == 0
    # Direct SQL also meets the live guard, proving it enforces the daily limit.
    with psycopg.connect(isolated_database) as connection:
        with pytest.raises(psycopg.errors.RaiseException, match='Daily appointment limit reached'):
            connection.execute('''INSERT INTO ramosolo.appointments
                (patient_id,doctor_id,starts_at,ends_at,occupied_until,status,service,institution_id,
                 care_type,visit_kind,schedule_version)
                VALUES (1,1,%s,%s,%s,'scheduled','General consultation',1,'outpatient','routine',1)''',
                (third_start, third_start + timedelta(minutes=30), third_start + timedelta(minutes=35)))
        connection.rollback()
        assert connection.execute("SELECT count(*) FROM ramosolo.appointments WHERE starts_at=%s", (third_start,)).fetchone()[0] == 0

    # Calendar proposal write and confirmed reschedule both persist history.
    proposed_start = utc_on(day, time(9, 10))
    proposal_response = client.post(f'/med/calendar/{db_identity(app, first_appointment_id)}/propose', data={
        'version': 1, 'starts_at': local(proposed_start), 'reason': 'Synthetic agreed proposal'})
    assert proposal_response.status_code == 302
    with app.app_context():
        assert db.session.scalar(select(func.count(AppointmentProposal.id)).where(
            AppointmentProposal.appointment_id == first_appointment_id,
            AppointmentProposal.state == 'pending')) == 1
        assert db.session.scalar(select(func.count(CalendarHistory.id)).where(
            CalendarHistory.appointment_id == first_appointment_id,
            CalendarHistory.action == 'proposal_created')) == 1

    moved_start = utc_on(day + timedelta(days=7), time(8))
    moved_response = client.post(f'/med/appointments/{first_appointment_id}/reschedule', data={
        'version': 1, 'confirmed': 'yes', 'reason': 'Synthetic confirmed reschedule',
        'starts_at': local(moved_start)})
    assert moved_response.status_code == 302
    with app.app_context():
        moved = db.session.get(Appointment, first_appointment_id)
        assert (moved.starts_at, moved.schedule_version, moved.visit_kind) == (moved_start, 2, 'routine')
        assert db.session.scalar(select(func.count(CalendarHistory.id)).where(
            CalendarHistory.appointment_id == first_appointment_id,
            CalendarHistory.action == 'staff_confirmed_change')) == 1
        old_job = db.session.execute(text('''SELECT state,invalidated_at,result_code FROM ramosolo.notification_outbox
            WHERE appointment_id=:id AND appointment_version=1'''), {'id': first_appointment_id}).one()
        assert old_job[0] == 'cancelled' and old_job[1] is not None and old_job[2] == 'appointment_changed'
        assert db.session.execute(text('''SELECT count(*) FROM ramosolo.notification_outbox
            WHERE appointment_id=:id AND appointment_version=2 AND state='pending' '''),
            {'id': first_appointment_id}).scalar_one() == 1

    assert client.get('/med/calendar').status_code == 200
    # Patient sees only their own appointments and cannot enter the staff calendar.
    patient_client = authenticated_app_client(app, '4:1', institution_id=1)
    patient_appointments = patient_client.get('/med/appointments')
    assert patient_appointments.status_code == 200
    assert b'Synthetic fixture patient B' not in patient_appointments.data
    assert patient_client.get('/med/calendar').status_code == 403
    # Another doctor in the same institution cannot read or book patient 1.
    peer_client = authenticated_app_client(app, '2:1', institution_id=1)
    peer_calendar = peer_client.get('/med/calendar')
    assert peer_calendar.status_code == 200 and b'Synthetic fixture patient A' not in peer_calendar.data
    assert peer_client.get('/med/patients/1').status_code == 404
    denied = peer_client.post('/med/appointments', data={'patient_id': 1,
        'starts_at': local(utc_on(day + timedelta(days=14), time(8))),
        'service': 'General consultation', 'care_type': 'outpatient', 'visit_kind': 'followup'})
    assert denied.status_code == 404
    # The same doctor identity selected in institution 2 sees only institution 2.
    other_institution = authenticated_app_client(app, '2:1', institution_id=2)
    other_calendar = other_institution.get('/med/calendar')
    assert other_calendar.status_code == 200 and b'Synthetic fixture patient C' in other_calendar.data
    assert b'Synthetic fixture patient A' not in other_calendar.data
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def db_identity(app, identity):
    with app.app_context():
        return db.session.get(Appointment, identity).id


def authenticated_app_client(app, user_id, institution_id):
    client = app.test_client()
    with client.session_transaction() as session:
        import time
        session['_user_id'] = user_id
        session['_fresh'] = True
        session['_auth_started_at'] = session['_auth_last_seen'] = int(time.time())
        session['institution_id'] = institution_id
    return client


@pytest.fixture(scope='module')
def local_pg():
    if not (BIN/'initdb.exe').exists():
        pytest.skip(f'Local PostgreSQL binaries unavailable at {BIN}; no remote fallback allowed')
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
            server_version, server_version_num = connection.execute(
                "SELECT current_setting('server_version'), current_setting('server_version_num')::integer"
            ).fetchone()
            print(f'Isolated synthetic PostgreSQL server: {server_version} (server_version_num={server_version_num})', flush=True)
            expected_major = os.environ.get('RAMOSOLO_POSTGRES_MAJOR')
            if expected_major and server_version_num // 10000 != int(expected_major):
                pytest.fail(f'Expected isolated PostgreSQL major {expected_major}; got {server_version}')
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
