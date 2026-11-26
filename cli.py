import secrets
from datetime import timedelta
import click
from flask import current_app
from sqlalchemy import select, text, inspect
from sqlalchemy.exc import SQLAlchemyError
from extensions import db
from models import User, Institution, Membership, Patient, Appointment, Admission, CareAssignment, ROLES
from medical_services import utcnow


def register_commands(app):
    @app.cli.command('deliver-email')
    @click.option('--live', is_flag=True, help='Explicitly use the approved Gmail pilot.')
    @click.option('--limit', type=click.IntRange(1, 100), default=25)
    def deliver_email(live, limit):
        """Drain portal email using the fake transport by default."""
        from mail_delivery import GmailProvider
        from security_email import FakeMailProvider, deliver_with_run
        if live:
            if (current_app.testing or db.engine.dialect.name != 'postgresql'
                    or current_app.config['MAIL_PROVIDER'] == 'fake'):
                raise click.ClickException('Live mode requires the approved PostgreSQL worker and Gmail settings.')
            from security_email import trusted_origin
            try:
                trusted_origin(current_app.config['AUTH_PUBLIC_URL'], https_only=True)
                provider = GmailProvider(current_app.config)
            except (TypeError, ValueError):
                raise click.ClickException('Gmail pilot configuration is incomplete or invalid.') from None
        else:
            if current_app.config['PRODUCTION'] or db.engine.dialect.name != 'sqlite':
                raise click.ClickException('Fake delivery is for disposable synthetic SQLite outboxes.')
            provider = FakeMailProvider()
        try:
            report = deliver_with_run(provider, limit=limit)
            click.echo(f'run={report.id} status={report.state} counters={report.counts}')
        except SQLAlchemyError:
            raise click.ClickException('Email worker database operation failed. Review the run ledger.') from None

    @app.cli.command('start-assisted-recovery')
    @click.option('--institution-id', type=int, required=True)
    @click.option('--user-id', type=int, required=True)
    @click.option('--requestor-id', type=int, required=True)
    @click.option('--approver-id', type=int, required=True)
    @click.option('--ticket', required=True, help='Opaque approved incident identifier.')
    @click.option('--replacement-email', help='Prompt for a separately approved replacement mailbox.', is_flag=True)
    @click.option('--reset-password', help='Prompt for a separately approved replacement password.', is_flag=True)
    def start_assisted_recovery(institution_id, user_id, requestor_id, approver_id, ticket, replacement_email,
                                reset_password):
        """Controlled recovery after identity proof and recorded dual approval."""
        from sqlalchemy.exc import IntegrityError
        from account_recovery import start_recovery
        address = click.prompt('Approved replacement mailbox', hide_input=True, confirmation_prompt=True) if replacement_email else None
        password = click.prompt('Replacement password', hide_input=True, confirmation_prompt=True) if reset_password else None
        proofs = []
        for label, identity in (('Requestor', requestor_id), ('Approver', approver_id)):
            proofs.append((identity, click.prompt(f'{label} password', hide_input=True),
                           click.prompt(f'{label} authenticator code', hide_input=True)))
        try:
            if start_recovery(institution_id, user_id, ticket, proofs, replacement_email=address,
                              new_password=password):
                click.echo('Recovery started. Email confirmation and the normal authenticator policy apply.')
                return
        except IntegrityError:
            db.session.rollback()
        raise click.ClickException('Recovery was not started. Check authority, identity proof, and account state.')

    @app.cli.command('deliver-security-email-fake')
    def deliver_security_email_fake():
        """Mark due synthetic security emails delivered without sending them."""
        from security_email import FakeMailProvider, deliver_pending
        if current_app.config['PRODUCTION'] or db.engine.dialect.name != 'sqlite':
            raise click.ClickException('Use a disposable local SQLite database with synthetic accounts.')
        click.echo(f'Synthetic messages delivered: {deliver_pending(FakeMailProvider())}')

    @app.cli.command('purge-expired-auth')
    def purge_expired_auth():
        """Remove expired authentication state."""
        from sqlalchemy import delete, or_
        from models import DeliveryLimit, OIDCExchange, PendingAuthentication, PhoneChallenge, PortalSession
        from portal_sessions import clock
        now = clock()
        db.session.execute(delete(PortalSession).where(or_(
            PortalSession.idle_expires_at <= now, PortalSession.absolute_expires_at <= now)))
        db.session.execute(delete(PendingAuthentication).where(PendingAuthentication.expires_at <= now))
        db.session.execute(delete(OIDCExchange).where(OIDCExchange.expires_at <= now))
        db.session.execute(delete(PhoneChallenge).where(PhoneChallenge.expires_at <= now))
        db.session.execute(delete(DeliveryLimit).where(DeliveryLimit.expires_at <= now))
        db.session.commit()
        click.echo('Expired authentication state removed.')

    @app.cli.command('check-connections')
    @click.option('--only', type=click.Choice(['database']), default='database')
    def check_connections(only):
        """Read-only database/configuration check; never initialize or migrate data."""
        from sqlalchemy.exc import SQLAlchemyError
        try:
            backend = db.engine.dialect.name
            schema = current_app.config['DB_SCHEMA'] if backend == 'postgresql' else None
            with db.engine.connect() as connection:
                transaction = connection.begin()
                try:
                    if backend == 'postgresql':
                        connection.execute(text('SET TRANSACTION READ ONLY'))
                        connection.execute(text("SET LOCAL statement_timeout = '10s'"))
                        active = connection.execute(text('SELECT current_schema()')).scalar_one()
                        if active != schema:
                            raise click.ClickException('Configured schema is not the active PostgreSQL schema. Check DB_SCHEMA, search_path and role permissions.')
                    inspector = inspect(connection)
                    existing = set(inspector.get_table_names(schema=schema))
                    missing = []
                    for table in db.metadata.sorted_tables:
                        if table.name not in existing:
                            missing.append(table.name + ' (table)')
                            continue
                        columns = {column['name'] for column in inspector.get_columns(table.name, schema=schema)}
                        missing.extend(table.name + '.' + name for name in table.columns.keys() if name not in columns)
                    if missing:
                        # These are model identifiers, never row values or URLs.
                        click.echo('Missing application objects: ' + ', '.join(sorted(missing)))
                        raise click.ClickException('Database schema is incomplete for this checkout. Review the current additive migrations; do not replay the baseline.')
                finally:
                    transaction.rollback()
            if backend == 'postgresql':
                click.echo('OK: PostgreSQL connected; application tables and columns found in schema ' + schema + '. No records changed.')
            else:
                click.echo('OK: Local SQLite application tables and columns found. Supabase is not selected.')
        except SQLAlchemyError:
            raise click.ClickException('Database check failed. Verify server-side URL, SSL, schema and runtime permissions. No credentials printed.') from None

    @app.cli.command('upgrade-calendar')
    def upgrade_calendar():
        """Explicit local-only additive upgrade; never migrate a remote database."""
        if current_app.config['PRODUCTION'] or db.engine.dialect.name!='sqlite':
            raise click.ClickException('Local SQLite only. Review migrations/009_assistant_calendar.sql for PostgreSQL after 007/008.')
        existing={c['name'] for c in inspect(db.engine).get_columns('appointments')} if inspect(db.engine).has_table('appointments') else set()
        additions={'ends_at':'DATETIME','occupied_until':'DATETIME','care_type':'VARCHAR(20)',
            'visit_kind':'VARCHAR(20)','schedule_version':'INTEGER NOT NULL DEFAULT 1',
            'hold_expires_at':'DATETIME','institution_id':'INTEGER REFERENCES institutions(id)'}
        if existing:
            for column,definition in additions.items():
                if column not in existing:
                    db.session.execute(text(f'ALTER TABLE appointments ADD COLUMN {column} {definition}'))
            db.session.commit()
        db.create_all()
        click.echo('Local calendar schema ready. No availability policy enabled, no invitation sent.')

    def local_coordination_columns():
        tables=inspect(db.engine).get_table_names()
        for table,index in [('admissions','admission_patient_identity'),('care_plans','care_plan_patient_identity')]:
            if table in tables:
                db.session.execute(text(f'CREATE UNIQUE INDEX IF NOT EXISTS {index} ON {table}(id,patient_id)'))
        db.session.commit()
        if 'continuity_notifications' in inspect(db.engine).get_table_names():
            existing={c['name'] for c in inspect(db.engine).get_columns('continuity_notifications')}
            additions={'purpose':"VARCHAR(30) NOT NULL DEFAULT 'administrative_contact'",
                'scope':"VARCHAR(200) NOT NULL DEFAULT 'practice'",
                'state':"VARCHAR(20) NOT NULL DEFAULT 'suppressed'",
                'result_code':"VARCHAR(80) NOT NULL DEFAULT 'legacy_consent_unverified'",
                'decision_id':'INTEGER REFERENCES communication_decisions(id)'}
            for column,definition in additions.items():
                if column not in existing:
                    db.session.execute(text(f'ALTER TABLE continuity_notifications ADD COLUMN {column} {definition}'))
            db.session.commit()

    @app.cli.command('upgrade-coordination')
    def upgrade_coordination():
        """Explicit local SQLite upgrade; never run PostgreSQL migrations automatically."""
        if current_app.config['PRODUCTION'] or db.engine.dialect.name!='sqlite':
            raise click.ClickException('Use the reviewed ramosolo 007/008 forward migrations; this command is SQLite only.')
        db.create_all()
        local_coordination_columns()
        click.echo('Local coordination tables initialized. No consent granted, no plan published, no communication sent.')

    @app.cli.command('upgrade-permissions')
    def upgrade_permissions():
        """Explicit local SQLite upgrade; PostgreSQL uses reviewed migration 003."""
        if current_app.config['PRODUCTION'] or db.engine.dialect.name != 'sqlite':
            raise click.ClickException('Use reviewed migrations/003_explicit_permissions.sql for PostgreSQL.')
        tables = inspect(db.engine).get_table_names()
        if 'care_plans' in tables:
            columns = {c['name'] for c in inspect(db.engine).get_columns('care_plans')}
            if 'patient_visible' not in columns:
                db.session.execute(text('ALTER TABLE care_plans ADD COLUMN patient_visible BOOLEAN NOT NULL DEFAULT 0'))
                db.session.commit()
        db.create_all()
        local_coordination_columns()
        click.echo('Local permission tables initialized. No access granted and no existing plans published.')

    @app.cli.command('init-db')
    def init_db():
        """Initialize NEW local database. Production uses the versioned SQL migration."""
        if current_app.config['PRODUCTION']:
            raise click.ClickException('Use migrations/001_initial_postgres.sql for a new production database.')
        if db.engine.dialect.name == 'postgresql':
            raise click.ClickException('For PostgreSQL use the reviewed versioned SQL migration, then bootstrap accounts.')
        db.create_all()
        click.echo('Local demo tables initialized. No accounts created.')

    @app.cli.command('seed-demo')
    def seed_demo():
        """Seed synthetic examples only into an EMPTY local SQLite database."""
        if current_app.config['PRODUCTION'] or db.engine.dialect.name != 'sqlite':
            raise click.ClickException('Demo seeding is only allowed in local SQLite.')
        db.create_all()
        if db.session.scalar(select(User.id).limit(1)):
            raise click.ClickException('Database is not empty. Existing records were not modified.')
        password = secrets.token_urlsafe(18)
        inst = Institution(name='Ramosolo · Demo practice', kind='medical', address='Pretoria · synthetic workspace')
        other = Institution(name='Second medical · Demo', kind='medical')
        edu = Institution(name='Le Sonto Education · Placeholder', kind='education')
        db.session.add_all([inst, other, edu]); db.session.flush()
        users = {}
        for role, name in [('admin','Demo Administrator'),('dr','Demo Dr Alex'),('nurse','Demo Nurse Sam'),('dr_assist','Demo Assistant Lee'),('patient','Demo Patient Jamie'),('dr2','Demo Dr Taylor')]:
            user = User(name=name, email=f'{role}@ramosolo.example')
            user.set_password(password); db.session.add(user); db.session.flush(); users[role] = user
            db.session.add(Membership(user_id=user.id, institution_id=inst.id, role='dr' if role=='dr2' else role,
                supervising_doctor_id=users['dr'].id if role=='dr_assist' else None))
        db.session.add(Membership(user_id=users['admin'].id, institution_id=edu.id, role='admin'))
        now = utcnow().replace(minute=0, second=0, microsecond=0)
        for i,name in enumerate(['Demo Jamie','Demo Morgan','Demo Casey','Demo Robin','Demo Jordan','Demo Riley','Demo Avery','Demo Quinn']):
            doctor = users['dr'] if i < 6 else users['dr2']
            p = Patient(name=name, email=f'patient{i}@example.test', phone='000 000 0000',
                institution_id=inst.id, doctor_id=doctor.id, user_id=users['patient'].id if i==0 else None)
            db.session.add(p); db.session.flush()
            if i < 6:
                seen = now - timedelta(days=[2,15,40,90,120,200][i])
                db.session.add(Appointment(patient_id=p.id, doctor_id=doctor.id, starts_at=seen,
                    status='completed', service='Individual therapy'))
            if i < 4:
                db.session.add(Appointment(patient_id=p.id, doctor_id=doctor.id,
                    starts_at=now+timedelta(days=1,hours=i), status='scheduled', service='Individual therapy'))
            if i in (0,2,6):
                db.session.add(Admission(patient_id=p.id, facility='Demo care facility', admitted_at=now-timedelta(days=2)))
            if i < 3:
                db.session.add(CareAssignment(patient_id=p.id, nurse_id=users['nurse'].id))
        db.session.commit()
        click.echo('Synthetic demo only. All demo accounts use this randomly generated password:')
        click.echo(password)
        for role in users:
            click.echo(f'{role}: {users[role].email}')
        click.echo('Do not expose these demo accounts publicly or use real patient information.')

    @app.cli.command('create-institution')
    @click.option('--name', prompt=True)
    @click.option('--kind', type=click.Choice(['medical','education']), prompt=True)
    def create_institution(name, kind):
        if not 2 <= len(name.strip()) <= 150:
            raise click.ClickException('Institution name must be 2–150 characters.')
        inst = Institution(name=name.strip(), kind=kind)
        db.session.add(inst); db.session.commit()
        click.echo(f'Created {kind} institution #{inst.id}.')

    @app.cli.command('create-admin')
    @click.option('--institution-id', type=int, prompt=True)
    @click.option('--name', prompt=True)
    @click.option('--email', prompt=True)
    @click.password_option()
    def create_admin(institution_id, name, email, password):
        from account_verification import issue, valid_address
        inst = db.session.get(Institution, institution_id)
        email = email.strip().lower()
        if not inst or len(password) < 12 or len(password) > 128 or not valid_address(email):
            raise click.ClickException('Check institution, email and password (12–128 characters).')
        if db.session.scalar(select(User.id).where(User.email==email.strip().lower())):
            raise click.ClickException('Account exists. Use add-membership instead.')
        user = User(name=name[:120], email=email.strip().lower()[:254]); user.set_password(password)
        db.session.add(user); db.session.flush()
        db.session.add(Membership(user_id=user.id, institution_id=inst.id, role='admin'))
        issue(user, email, initial=True)
        db.session.commit(); click.echo('Administrator created. Email confirmation is required.')

    @app.cli.command('add-membership')
    @click.option('--email', prompt=True)
    @click.option('--institution-id', type=int, prompt=True)
    @click.option('--role', type=click.Choice(list(ROLES)), prompt=True)
    @click.option('--doctor-id', type=int)
    def add_membership(email, institution_id, role, doctor_id):
        from account_verification import welcome_if_active
        user = db.session.scalar(select(User).where(User.email==email.strip().lower()).with_for_update())
        inst = db.session.get(Institution, institution_id)
        if not user or not inst:
            raise click.ClickException('Unknown user or institution.')
        if db.session.scalar(select(Membership.id).where(Membership.user_id==user.id,Membership.institution_id==inst.id)):
            raise click.ClickException('Membership already exists. Edit only through a reviewed owner migration.')
        if role in ('patient','dr_assist'):
            doctor = db.session.scalar(select(Membership).where(Membership.user_id==doctor_id,
                Membership.institution_id==inst.id,Membership.role=='dr',Membership.enabled.is_(True)))
            if not doctor or inst.kind != 'medical':
                raise click.ClickException('A medical doctor in the same institution is required.')
        db.session.add(Membership(user_id=user.id,institution_id=inst.id,role=role,
            supervising_doctor_id=doctor_id if role=='dr_assist' else None))
        if role=='patient':
            db.session.add(Patient(institution_id=inst.id,user_id=user.id,doctor_id=doctor_id,name=user.name,email=user.email))
        user.session_version += 1
        welcome_if_active(user)
        db.session.commit(); click.echo('Membership added. Confirm identity before sharing access.')

    @app.cli.command('reset-password')
    @click.option('--email', prompt=True)
    @click.password_option()
    def reset_password(email, password):
        if not current_app.testing or db.engine.dialect.name != 'sqlite':
            raise click.ClickException('Use the dual-control start-assisted-recovery command for account recovery.')
        from security_email import enqueue
        user = db.session.scalar(select(User).where(User.email==email.strip().lower()).with_for_update())
        if not user or not 12 <= len(password) <= 128:
            raise click.ClickException('Unknown account or invalid password length.')
        user.set_password(password); user.failed_logins=0; user.locked_until=None
        enqueue(user, 'change', f'credentials:{user.id}:{user.session_version}',
                detail='The practice operator reset the sign-in password.')
        db.session.commit(); click.echo('Password reset. Verify identity before delivering it.')
