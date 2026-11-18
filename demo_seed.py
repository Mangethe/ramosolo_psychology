"""Repeatable ORM-only synthetic fixtures, with explicit provenance and no delivery."""
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

import click
from sqlalchemy import select, text, func
from extensions import db
from database_schema import active_schema_matches, configured_schema, schema_diagnostics
import models as m
from medical_services import TZ, statistics

PROJECT = 'mavpwgqjgjnvopnnqnmb'


def protected_handoff(directory, accounts):
    """Create a new private directory before writing any password material."""
    directory = Path(directory).resolve()
    if directory.is_relative_to(Path(__file__).resolve().parent):
        raise click.ClickException('Keep the protected handoff outside the repository.')
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    if os.name == 'nt':
        identity = subprocess.run(['whoami'], capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(['icacls', str(directory), '/inheritance:r', '/grant:r',
                        identity + ':(OI)(CI)F'], capture_output=True, check=True)
    else:
        directory.chmod(0o700)
    target = directory / 'accounts.json'
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as output:
        json.dump(accounts, output, indent=2)
    return target


def target_check(expected_project, diagnose_schema=False):
    if db.engine.dialect.name != 'postgresql':
        raise click.ClickException('This command requires the hosted PostgreSQL database.')
    url = db.engine.url
    # Do not display the URL, username, password or raw driver errors.
    if expected_project != PROJECT or not (
        url.host == f'db.{PROJECT}.supabase.co' or
        (url.host and url.host.endswith('.pooler.supabase.com') and url.username == f'postgres.{PROJECT}')
    ):
        raise click.ClickException('Connection does not identify the approved Supabase project.')
    if configured_schema() != 'ramosolo':
        raise click.ClickException('Expected DB_SCHEMA=ramosolo for this hosted dataset.')
    connection = db.session.connection()
    if diagnose_schema:
        schema_diagnostics(db.engine, 'seeder-transaction', connection)
    if not active_schema_matches(connection):
        raise click.ClickException('Expected ramosolo as the active schema.')
    if connection.execute(text('SELECT max(version) FROM "ramosolo".schema_versions')).scalar_one() != 6:
        raise click.ClickException('Apply the reviewed v6 additive migration first.')


def manifest_rows(dataset):
    tables = {mapper.local_table.name: mapper.class_ for mapper in db.Model.registry.mappers}
    result = {}
    for table, ids in dataset.manifest['tables'].items():
        rows = list(db.session.scalars(select(tables[table]).where(tables[table].id.in_(ids))))
        if len(rows) != len(ids):
            raise click.ClickException(f'Dataset provenance is incomplete in {table}; no records changed.')
        result[table] = rows
    return result


def verify_dataset(dataset):
    rows = manifest_rows(dataset)
    owned = {row.id for row in rows['institutions']}
    assert all(row.demo_dataset_id == dataset.id for row in rows['institutions'])
    users = {row.id for row in rows['users']}
    memberships = {(row.user_id, row.institution_id): row for row in rows['memberships']}
    patients = {row.id: row for row in rows['patients']}
    for row in rows['patients']:
        assert row.institution_id in owned and row.user_id in users and row.doctor_id in users
        assert memberships[row.doctor_id, row.institution_id].role == 'dr'
        assert memberships[row.user_id, row.institution_id].role == 'patient'
    for row in rows.get('care_assignments', []):
        assert memberships[row.nurse_id, patients[row.patient_id].institution_id].role == 'nurse'
    for row in rows['memberships']:
        assert row.institution_id in owned and row.user_id in users
        if row.role == 'dr_assist':
            assert memberships[row.supervising_doctor_id, row.institution_id].role == 'dr'
    for row in rows['appointments']:
        patient = patients[row.patient_id]
        assert (row.institution_id, row.doctor_id) == (patient.institution_id, patient.doctor_id)
    # Check every manifest object's actual mapped FK, without fetching real rows.
    for objects in rows.values():
        for row in objects:
            for column in row.__table__.columns:
                value = getattr(row, column.name)
                for fk in column.foreign_keys:
                    if value is not None:
                        assert db.session.scalar(select(func.count()).select_from(fk.column.table).where(fk.column == value)) == 1
    totals = {}
    for inst in rows['institutions']:
        if inst.kind == 'medical':
            totals[str(inst.id)] = statistics([p for p in patients.values() if p.institution_id == inst.id])[0]
    return {'dataset': dataset.name, 'counts': {name: len(values) for name, values in sorted(rows.items())},
            'roles': dict(Counter(row.role for row in rows['memberships'])), 'dashboards': totals,
            'foreign_keys_verified': True}


def seed_dataset(name, handoff_directory):
    """One transaction; reruns use the manifest exclusively, never names/emails."""
    if not re.fullmatch(r'[a-z][a-z0-9-]{2,49}', name):
        raise click.ClickException('Dataset name must be 3–50 lowercase letters, numbers or hyphens.')
    if db.engine.dialect.name == 'postgresql':
        db.session.execute(text('select pg_advisory_xact_lock(7015, 600)'))
    existing = db.session.scalar(select(m.DemoDataset).where(m.DemoDataset.name == name))
    if existing:
        if not existing.complete:
            raise click.ClickException('Incomplete dataset; manual reconciliation required.')
        result = verify_dataset(existing)
        db.session.rollback()
        return result, None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if db.engine.dialect.name == 'postgresql':
        now = db.session.scalar(text("select timezone('UTC', clock_timestamp())"))
    today = now.replace(tzinfo=timezone.utc).astimezone(TZ).date()
    dataset = m.DemoDataset(name=name, anchor_date=today, manifest={})
    db.session.add(dataset); db.session.flush()
    manifest = {}
    accounts = []

    def add(cls, **values):
        row = cls(**values)
        db.session.add(row); db.session.flush()
        manifest.setdefault(cls.__tablename__, []).append(row.id)
        return row

    inst = add(m.Institution, name=f'Fictional {name} Medical A', kind='medical',
               address='Fictional demo address; no physical practice', demo_dataset_id=dataset.id)
    other = add(m.Institution, name=f'Fictional {name} Medical B', kind='medical', demo_dataset_id=dataset.id)
    edu = add(m.Institution, name=f'Fictional {name} Education placeholder', kind='education', demo_dataset_id=dataset.id)

    def account(key, role, institution, doctor=None):
        password = secrets.token_urlsafe(24)
        # A collision aborts the transaction; existing accounts are never adopted.
        user = m.User(name='Fictional Demo ' + key, email=f'{name}.{key}@example.test')
        user.set_password(password)
        db.session.add(user); db.session.flush()
        manifest.setdefault('users', []).append(user.id)
        add(m.Membership, user_id=user.id, institution_id=institution.id, role=role,
            supervising_doctor_id=doctor.id if doctor else None)
        accounts.append({'email': user.email, 'password': password, 'role': role, 'institution_id': institution.id})
        return user

    admin = account('admin', 'admin', inst)
    doctor = account('doctor-a', 'dr', inst)
    doctor2 = account('doctor-b', 'dr', inst)
    foreign = account('doctor-c', 'dr', other)
    nurse = account('nurse', 'nurse', inst)
    account('assistant', 'dr_assist', inst, doctor)
    add(m.Membership, user_id=admin.id, institution_id=edu.id, role='admin')
    patients = []
    for i in range(30):
        institution = inst if i < 27 else other
        assigned = doctor if i < 20 else doctor2 if i < 27 else foreign
        user = account(f'patient-{i+1:02}', 'patient', institution)
        patient = add(m.Patient, institution_id=institution.id, user_id=user.id, doctor_id=assigned.id,
                      name=user.name, email=user.email, phone='')
        patients.append(patient)
        if i < 10:
            add(m.CareAssignment, patient_id=patient.id, nurse_id=nurse.id)
        add(m.CommunicationPreference, institution_id=institution.id, patient_id=patient.id,
            changed_by=user.id, in_app_enabled=False, email_enabled=False, sms_enabled=False)

    def at(day, hour, minute=0):
        return datetime.combine(day, time(hour, minute), TZ).astimezone(timezone.utc).replace(tzinfo=None)

    policies = {}
    for user, institution in [(doctor, inst), (doctor2, inst), (foreign, other)]:
        policy = add(m.AvailabilityPolicy, institution_id=institution.id, doctor_id=user.id,
                     daily_limit=3, enabled=True, holidays_confirmed=True, horizon_days=90)
        policies[user.id] = policy
        # Explicit fictional hours belong only to these marked demo institutions.
        for weekday in [0, 1, 2, 4]:
            add(m.AvailabilitySession, policy_id=policy.id, weekday=weekday, care_type='inpatient',
                opens_at=time(8), closes_at=time(10), duration_minutes=25, first_minutes=60,
                assessment_minutes=60, break_minutes=5)
        add(m.AvailabilitySession, policy_id=policy.id, weekday=2, care_type='outpatient',
            opens_at=time(11), closes_at=time(15), duration_minutes=45, first_minutes=60,
            assessment_minutes=60, break_minutes=5)

    def appointment(patient, day, hour, minute=0, status='completed', care='outpatient'):
        starts = at(day, hour, minute)
        duration = 45 if care == 'outpatient' else 25
        if status == 'scheduled':
            from Med.MedWebsite.booking import slot_details
            _, ends, occupied = slot_details(patient.institution_id, patient.doctor_id, starts, care, 'routine', patient.id)
        else:
            ends, occupied = starts + timedelta(minutes=duration), starts + timedelta(minutes=duration+5)
        return add(m.Appointment, institution_id=patient.institution_id, patient_id=patient.id,
            doctor_id=patient.doctor_id, starts_at=starts, ends_at=ends, occupied_until=occupied,
            care_type=care, visit_kind='routine', status=status, was_confirmed=True, service='General consultation')

    # Ten active, ten inactive and ten never-seen, distributed across scopes.
    for i, patient in enumerate(patients):
        if i < 20:
            day = today - timedelta(days=7*(1+i//3) if i < 10 else 140+7*(i//3))
            day -= timedelta(days=(day.weekday()-2) % 7)
            slot = (i % 3)*50
            appointment(patient, day, 11+slot//60, slot%60)
        if i < 4:
            add(m.Admission, patient_id=patient.id, facility='Fictional demo facility', admitted_at=now-timedelta(days=2))
        elif i < 7:
            add(m.Admission, patient_id=patient.id, facility='Fictional demo facility',
                admitted_at=now-timedelta(days=45), discharged_at=now-timedelta(days=40))
    wednesday = today + timedelta(days=(2-today.weekday()) % 7 or 7)
    if (wednesday-today).days < 3:
        wednesday += timedelta(days=7)
    # Capacity example: three bookings reach Doctor A's Wednesday daily limit.
    future = [appointment(patients[i], wednesday, 11, i*50, status='scheduled') for i in range(2)]
    future.append(appointment(patients[2], wednesday, 8, status='scheduled', care='inpatient'))
    for weekday, index in [(0,3),(1,4),(4,5)]:
        day = today + timedelta(days=(weekday-today.weekday()) % 7 or 7)
        future.append(appointment(patients[index], day, 8, status='scheduled', care='inpatient'))
    future.append(appointment(patients[20], wednesday, 11, status='scheduled'))
    future.append(appointment(patients[27], wednesday, 11, status='scheduled'))
    past = wednesday-timedelta(days=14)
    appointment(patients[6], past, 12, status='cancelled')
    appointment(patients[7], past, 13, status='no_show')
    holiday = wednesday+timedelta(days=7)
    add(m.PublicHoliday, institution_id=inst.id, day=holiday, label='Fictional demo closure (not an official holiday)')
    exception_day = holiday+timedelta(days=1)
    add(m.AvailabilityException, policy_id=policies[doctor.id].id, day=exception_day, kind='opening',
        care_type='inpatient', opens_at=time(8), closes_at=time(10), duration_minutes=25,
        first_minutes=60, assessment_minutes=60, break_minutes=5, override_closure=True,
        approved_by=admin.id, approved_at=now, reason='Fictional demo authorized Thursday opening')
    appointment(patients[8], exception_day, 8, status='scheduled', care='inpatient')
    for i in range(4):
        # Illustrative accounting units only; these are not practice fees.
        appt = future[i]
        invoice = add(m.Invoice, institution_id=inst.id, doctor_id=doctor.id,
                      appointment_id=appt.id, total=Decimal('100.00'), created_by=admin.id)
        if i != 2:
            receipt = add(m.PaymentEntry, invoice_id=invoice.id, institution_id=inst.id, kind='receipt',
                amount=Decimal('50.00') if i == 1 else Decimal('100.00'), method='other', reason='received',
                effective_at=now-timedelta(minutes=1), actor_id=admin.id,
                submission_key=secrets.token_hex(32), submission_fingerprint=secrets.token_hex(32))
            if i == 3:
                add(m.PaymentEntry, invoice_id=invoice.id, institution_id=inst.id, kind='refund',
                    amount=Decimal('100.00'), method='other', reason='refund', original_receipt_id=receipt.id,
                    effective_at=now, actor_id=admin.id, submission_key=secrets.token_hex(32),
                    submission_fingerprint=secrets.token_hex(32))
    for institution, actor in [(inst, admin), (other, foreign)]:
        # Only the primary institution has an administrator for policy governance.
        if institution.id == inst.id:
            policy = add(m.ReminderPolicy, institution_id=inst.id, enabled=False, updated_by=actor.id)
            add(m.ReminderLead, policy_id=policy.id, minutes=1440)
            add(m.FollowupPolicy, institution_id=inst.id, updated_by=actor.id, enabled=True)
    appt = future[0]
    add(m.AppointmentConfirmation, institution_id=inst.id, appointment_id=appt.id,
        appointment_version=appt.schedule_version, scheduled_start=appt.starts_at,
        deadline=appt.starts_at-timedelta(hours=24), requested_at=now,
        requested_by=admin.id, policy_version=1)
    add(m.AttendanceFollowup, institution_id=inst.id, appointment_id=appt.id,
        appointment_version=appt.schedule_version, rule='confirmation_due', policy_version=1,
        reason='Fictional administrative demo; review nearer confirmation deadline',
        suggested_action='Review the synthetic appointment confirmation', evidence={'synthetic': True}, state='open')
    # Build a genuine, consent-scoped pending in-app job, then cancel it by
    # disabling its policy. No adapter or live worker is invoked.
    policy = db.session.scalar(select(m.ReminderPolicy).where(m.ReminderPolicy.institution_id==inst.id))
    policy.enabled=True
    db.session.flush(); db.session.refresh(policy)
    pref = db.session.scalar(select(m.CommunicationPreference).where(m.CommunicationPreference.patient_id==appt.patient_id))
    pref.in_app_enabled=True; pref.in_app_consent_at=now
    db.session.flush(); db.session.refresh(pref)
    due=appt.starts_at-timedelta(minutes=1440)
    job=add(m.NotificationJob, institution_id=inst.id, appointment_id=appt.id,
        appointment_version=appt.schedule_version, scheduled_start=appt.starts_at,
        preference_id=pref.id, recipient_user_id=patients[0].user_id,
        preference_version=pref.version, consent_at=pref.in_app_consent_at,
        policy_id=policy.id, policy_version=policy.version, lead_minutes=1440,
        channel='in_app', due_at=due, next_attempt_at=due, max_attempts=policy.max_attempts)
    policy.enabled=False
    db.session.flush()
    # SQLite invalidation hook and hosted PostgreSQL trigger both cancel the job.
    db.session.refresh(job)
    assert job.state=='cancelled'
    # Trigger-created history is part of the named dataset too.
    for cls in [m.AuditEvent, m.AttendanceEvent]:
        query = select(cls.id).where(cls.institution_id.in_([inst.id, other.id]))
        manifest[cls.__tablename__] = list(db.session.scalars(query))
    dataset.manifest = {'tables': manifest, 'fixture_version': 1}
    dataset.complete = True
    db.session.flush()
    result = verify_dataset(dataset)
    target = protected_handoff(handoff_directory, accounts)
    try:
        db.session.commit()
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return result, target


def register_demo_command(app):
    @app.cli.command('verify-demo')
    @click.option('--dataset', default='ramosolo-demo-v1')
    @click.option('--expected-project', required=True)
    @click.option('--handoff-file', required=True, type=click.Path(exists=True, path_type=Path))
    def verify_demo(dataset, expected_project, handoff_file):
        """Verify hosted fixtures and actual CSRF-protected logins using the private handoff."""
        try:
            target_check(expected_project)
            row = db.session.scalar(select(m.DemoDataset).where(m.DemoDataset.name==dataset, m.DemoDataset.complete.is_(True)))
            if not row:
                raise click.ClickException('Named dataset not found.')
            result = verify_dataset(row)
            rows = manifest_rows(row)
            owned = {user.email: user for user in rows['users']}
            accounts = json.loads(handoff_file.read_text(encoding='utf-8'))
            if {a['email'] for a in accounts} != set(owned):
                raise click.ClickException('Handoff does not match this dataset.')
            from flask import g
            from flask_login import login_user
            from access import patient_scope, appointment_scope
            checked = Counter()

            def request(client, method, path, **kwargs):
                # CLI commands retain an app context. Each simulated request
                # needs its own g, just as a request to the deployed app does:
                # Flask-Login and Flask-WTF cache user/CSRF state there.
                with app.app_context():
                    return getattr(client, method)(path, **kwargs)

            for account in accounts:
                user = owned[account['email']]
                membership = next(mem for mem in rows['memberships']
                    if mem.user_id==user.id and mem.institution_id==account['institution_id'])
                with app.test_request_context('/med'):
                    login_user(user)
                    g.membership = membership
                    visible = {p.id for p in db.session.scalars(patient_scope())}
                    if membership.role=='admin':
                        expected={p.id for p in rows['patients'] if p.institution_id==membership.institution_id}
                    elif membership.role in ('dr','dr_assist'):
                        doctor=user.id if membership.role=='dr' else membership.supervising_doctor_id
                        expected={p.id for p in rows['patients'] if p.institution_id==membership.institution_id and p.doctor_id==doctor}
                    elif membership.role=='nurse':
                        expected={c.patient_id for c in rows['care_assignments'] if c.nurse_id==user.id}
                    else:
                        expected={p.id for p in rows['patients'] if p.user_id==user.id and p.institution_id==membership.institution_id}
                    assert visible==expected
                    assert {a.id for a in db.session.scalars(appointment_scope())} == {
                        a.id for a in rows['appointments'] if a.patient_id in expected}
                g.pop('_login_user',None)
                client=app.test_client()
                page=request(client, 'get', '/auth/login')
                csrf=re.search(rb'name="csrf_token"[^>]*value="([^"]+)"',page.data)
                assert csrf, 'CSRF must remain enabled during hosted verification'
                g.pop('_login_user',None)
                response=request(client, 'post', '/auth/login',data={'email':account['email'], 'password':account['password'],
                    'csrf_token':csrf.group(1).decode()})
                assert response.status_code==302
                g.pop('_login_user',None)
                from flask import template_rendered
                rendered = []
                def capture_dashboard(sender, template, context, **extra):
                    if template.name == 'medical/dashboard.html':
                        rendered.append(context['stats'])
                with template_rendered.connected_to(capture_dashboard, app):
                    assert request(client, 'get', '/med').status_code==200
                assert rendered == [statistics([p for p in rows['patients'] if p.id in expected])[0]]
                g.pop('_login_user',None)
                assert request(client, 'get', '/admin/users').status_code==(200 if membership.role=='admin' else 403)
                g.pop('_login_user',None)
                assert request(client, 'get', '/med/patients').status_code==(403 if membership.role=='patient' else 200)
                g.pop('_login_user',None)
                for patient in rows['patients']:
                    if patient.id not in expected and membership.role!='patient':
                        assert request(client, 'get', f'/med/patients/{patient.id}').status_code==404
                        g.pop('_login_user',None)
                checked[membership.role]+=1
            result['csrf_protected_logins_verified']=dict(checked)
            result['assignment_and_institution_isolation_verified']=True
            result['rendered_dashboard_totals_verified']=True
            click.echo(json.dumps(result,indent=2))
        except click.ClickException:
            raise
        except Exception:
            db.session.rollback()
            raise click.ClickException('Hosted demo verification failed; no credentials or raw errors displayed.') from None

    @app.cli.command('seed-demo')
    @click.option('--dataset', default='ramosolo-demo-v1', show_default=True)
    @click.option('--expected-project', required=True)
    @click.option('--handoff-directory', required=True, type=click.Path(path_type=Path))
    @click.option('--diagnose-schema', is_flag=True, help='Print only schema metadata to stderr.')
    def seed_demo(dataset, expected_project, handoff_directory, diagnose_schema):
        """Add a named synthetic dataset to the approved hosted project; safely rerunnable."""
        try:
            target_check(expected_project, diagnose_schema=diagnose_schema)
            result, handoff = seed_dataset(dataset, handoff_directory)
            click.echo(json.dumps(result, indent=2))
            click.echo(f'Protected account handoff: {handoff}' if handoff else 'Existing dataset verified; credentials unchanged.')
        except (click.ClickException, AssertionError):
            db.session.rollback()
            raise
        except Exception:
            db.session.rollback()
            raise click.ClickException('Synthetic seed stopped; transaction rolled back. No connection details logged.') from None
