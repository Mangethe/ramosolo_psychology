import secrets
from datetime import timedelta
import click
from flask import current_app
from sqlalchemy import select, text, inspect
from extensions import db
from models import User, Institution, Membership, Patient, Appointment, Admission, CareAssignment, ROLES
from medical_services import utcnow


def register_commands(app):
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
        inst = db.session.get(Institution, institution_id)
        if not inst or len(password) < 12 or len(password) > 128 or '@' not in email:
            raise click.ClickException('Check institution, email and password (12–128 characters).')
        if db.session.scalar(select(User.id).where(User.email==email.strip().lower())):
            raise click.ClickException('Account exists. Use add-membership instead.')
        user = User(name=name[:120], email=email.strip().lower()[:254]); user.set_password(password)
        db.session.add(user); db.session.flush()
        db.session.add(Membership(user_id=user.id, institution_id=inst.id, role='admin'))
        db.session.commit(); click.echo('Administrator created.')

    @app.cli.command('add-membership')
    @click.option('--email', prompt=True)
    @click.option('--institution-id', type=int, prompt=True)
    @click.option('--role', type=click.Choice(list(ROLES)), prompt=True)
    @click.option('--doctor-id', type=int)
    def add_membership(email, institution_id, role, doctor_id):
        user = db.session.scalar(select(User).where(User.email==email.strip().lower()))
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
        db.session.commit(); click.echo('Membership added. Confirm identity before sharing access.')

    @app.cli.command('reset-password')
    @click.option('--email', prompt=True)
    @click.password_option()
    def reset_password(email, password):
        user = db.session.scalar(select(User).where(User.email==email.strip().lower()))
        if not user or not 12 <= len(password) <= 128:
            raise click.ClickException('Unknown account or invalid password length.')
        user.set_password(password); user.failed_logins=0; user.locked_until=None
        db.session.commit(); click.echo('Password reset. Verify identity before delivering it.')
