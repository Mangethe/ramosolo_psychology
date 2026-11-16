"""Operational scheduling only. Existing availability table names are retained."""
from extensions import db
from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AvailabilityPolicy(db.Model):
    __tablename__ = 'availability_policies'
    __table_args__ = (db.UniqueConstraint('institution_id', 'doctor_id'),)
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    daily_limit = db.Column(db.Integer, nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=False)
    holidays_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    horizon_days = db.Column(db.Integer, nullable=False, default=90)
    hold_minutes = db.Column(db.Integer, nullable=False, default=10)


class AvailabilitySession(db.Model):
    __tablename__ = 'availability_sessions'
    __table_args__ = (db.CheckConstraint("(care_type='outpatient' AND weekday=2) OR (care_type='inpatient' AND weekday IN (0,1,2,4))"),
        db.CheckConstraint("opens_at < closes_at AND first_minutes BETWEEN 60 AND 120 AND assessment_minutes BETWEEN 1 AND 240 AND break_minutes BETWEEN 5 AND 10"),
        db.CheckConstraint("(care_type='outpatient' AND duration_minutes BETWEEN 30 AND 60) OR (care_type='inpatient' AND duration_minutes BETWEEN 20 AND 30)"))
    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey('availability_policies.id'), nullable=False)
    weekday = db.Column(db.Integer, nullable=False)
    care_type = db.Column(db.String(20), nullable=False)
    opens_at = db.Column(db.Time, nullable=False)
    closes_at = db.Column(db.Time, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    first_minutes = db.Column(db.Integer, nullable=False)
    assessment_minutes = db.Column(db.Integer, nullable=False)
    break_minutes = db.Column(db.Integer, nullable=False)


class AvailabilityException(db.Model):
    __tablename__ = 'availability_exceptions'
    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey('availability_policies.id'), nullable=False)
    day = db.Column(db.Date, nullable=False)
    kind = db.Column(db.String(20), nullable=False)
    care_type = db.Column(db.String(20))
    opens_at = db.Column(db.Time)
    closes_at = db.Column(db.Time)
    duration_minutes = db.Column(db.Integer)
    first_minutes = db.Column(db.Integer)
    assessment_minutes = db.Column(db.Integer)
    break_minutes = db.Column(db.Integer)
    override_closure = db.Column(db.Boolean, nullable=False, default=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reason = db.Column(db.String(240), nullable=False)
    approved_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class PublicHoliday(db.Model):
    __tablename__ = 'public_holidays'
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    day = db.Column(db.Date, nullable=False)
    label = db.Column(db.String(120), nullable=False)


class CalendarBlock(db.Model):
    __tablename__ = 'calendar_blocks'
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(30), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    released_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    released_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class CalendarDelegation(db.Model):
    __tablename__ = 'calendar_delegations'
    __table_args__ = (db.UniqueConstraint('institution_id', 'doctor_id', 'assistant_id'),)
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assistant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)


class AppointmentProposal(db.Model):
    __tablename__ = 'appointment_proposals'
    __table_args__ = (db.CheckConstraint("state IN ('pending','accepted','declined','expired','superseded')"),
        db.Index('one_pending_appointment_proposal', 'appointment_id', unique=True,
            sqlite_where=db.text("state='pending'"), postgresql_where=db.text("state='pending'")))
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    base_version = db.Column(db.Integer, nullable=False)
    original_at = db.Column(db.DateTime, nullable=False)
    proposed_at = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(240), nullable=False)
    state = db.Column(db.String(20), nullable=False, default='pending')
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    responded_at = db.Column(db.DateTime)
    token_digest = db.Column(db.String(64), unique=True, nullable=False)
    code_digest = db.Column(db.String(64), nullable=False)
    communication_decision_id = db.Column(db.Integer, db.ForeignKey('communication_decisions.id'))
    verification_attempts = db.Column(db.Integer, nullable=False, default=0)


class CalendarHistory(db.Model):
    __tablename__ = 'calendar_history'
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'))
    block_id = db.Column(db.Integer, db.ForeignKey('calendar_blocks.id'))
    proposal_id = db.Column(db.Integer, db.ForeignKey('appointment_proposals.id'))
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(40), nullable=False)
    original_at = db.Column(db.DateTime)
    new_at = db.Column(db.DateTime)
    reason = db.Column(db.String(240), nullable=False, default='')
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
