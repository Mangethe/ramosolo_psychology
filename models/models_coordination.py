"""Source records for care coordination. My actions is a projection, not a task store."""
from datetime import datetime, timezone
from extensions import db


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CoordinationCoverage(db.Model):
    """Explicit, time-limited covering-clinician assignment; no general chart access."""
    __tablename__ = 'coordination_coverage'
    __table_args__ = (db.CheckConstraint("kind IN ('discharge','referral','review')"),
        db.CheckConstraint("status IN ('granted','withdrawn')"),
        db.CheckConstraint("status <> 'granted' OR valid_until IS NOT NULL"),
        db.Index('coordination_coverage_lookup','institution_id','patient_id','user_id','kind','id'))
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    kind = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    valid_until = db.Column(db.DateTime)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)


class CoordinationPolicy(db.Model):
    __tablename__ = 'coordination_policies'
    __table_args__ = (db.UniqueConstraint('institution_id', 'kind', 'version'),
        db.CheckConstraint("kind IN ('discharge','review')"),
        db.CheckConstraint('deadline_hours > 0 AND due_soon_days >= 0'))
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    kind = db.Column(db.String(20), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    deadline_hours = db.Column(db.Integer, nullable=False)
    due_soon_days = db.Column(db.Integer, nullable=False)
    instructions = db.Column(db.String(1500), nullable=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_at = db.Column(db.DateTime, nullable=False, default=now)


class DischargeFollowup(db.Model):
    __tablename__ = 'discharge_followups'
    __table_args__ = (db.UniqueConstraint('admission_id'),
        db.ForeignKeyConstraint(['admission_id','patient_id'],['admissions.id','admissions.patient_id'],name='discharge_episode_patient_match'),
        db.CheckConstraint("status IN ('open','contacted','completed','cancelled')"),
        db.CheckConstraint("NOT planning_complete OR (owner_id IS NOT NULL AND due_at IS NOT NULL AND policy_id IS NOT NULL)"),
        db.CheckConstraint("status <> 'completed' OR (outcome <> '' AND closure_reason <> '')"))
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, index=True)
    admission_id = db.Column(db.Integer, db.ForeignKey('admissions.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    cover_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    team = db.Column(db.String(120), nullable=False, default='')
    due_at = db.Column(db.DateTime)
    policy_id = db.Column(db.Integer, db.ForeignKey('coordination_policies.id'))
    planning_complete = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default='open')
    outcome = db.Column(db.String(1500), nullable=False, default='')
    closure_reason = db.Column(db.String(1000), nullable=False, default='')
    escalated = db.Column(db.Boolean, nullable=False, default=False)
    owner_unavailable = db.Column(db.Boolean, nullable=False, default=False)
    patient_visible = db.Column(db.Boolean, nullable=False, default=False)
    agreed_action = db.Column(db.String(1000), nullable=False, default='')
    version = db.Column(db.Integer, nullable=False, default=1)
    updated_at = db.Column(db.DateTime, nullable=False, default=now)


class Referral(db.Model):
    __tablename__ = 'care_referrals'
    __table_args__ = (db.UniqueConstraint('institution_id','patient_id','submission_key'),
        db.CheckConstraint("direction IN ('incoming','outgoing')"),
        db.CheckConstraint("status IN ('draft','sent','acknowledged','accepted','appointment_arranged','completed','declined','cancelled')"))
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, index=True)
    direction = db.Column(db.String(20), nullable=False)
    other_party = db.Column(db.String(200), nullable=False)
    practitioner_id = db.Column(db.Integer, db.ForeignKey('external_practitioners.id'))
    referred_at = db.Column(db.DateTime, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    cover_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    due_at = db.Column(db.DateTime)
    requested_action = db.Column(db.String(1500), nullable=False)
    next_action = db.Column(db.String(1000), nullable=False, default='')
    outstanding_information = db.Column(db.String(1000), nullable=False, default='')
    consent_id = db.Column(db.Integer, db.ForeignKey('communication_decisions.id'))
    status = db.Column(db.String(30), nullable=False, default='draft')
    response_at = db.Column(db.DateTime)
    appointment_at = db.Column(db.DateTime)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'))
    completed_at = db.Column(db.DateTime)
    closure_reason = db.Column(db.String(1000), nullable=False, default='')
    owner_unavailable = db.Column(db.Boolean, nullable=False, default=False)
    escalated = db.Column(db.Boolean, nullable=False, default=False)
    patient_visible = db.Column(db.Boolean, nullable=False, default=False)
    submission_key = db.Column(db.String(64), nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    updated_at = db.Column(db.DateTime, nullable=False, default=now)


class ReferralClinical(db.Model):
    __tablename__ = 'referral_clinical_records'
    id = db.Column(db.Integer, primary_key=True)
    referral_id = db.Column(db.Integer, db.ForeignKey('care_referrals.id'), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)


class CommunicationDecision(db.Model):
    """Append-only purpose/channel/scope consent and destination snapshots."""
    __tablename__ = 'communication_decisions'
    __table_args__ = (db.CheckConstraint("purpose IN ('reminders','administrative_contact','referral_sharing','care_plan_sharing')"),
        db.CheckConstraint("channel IN ('portal','phone','email','sms')"),
        db.CheckConstraint("status IN ('granted','declined','withdrawn')"),
        db.Index('communication_decision_lookup','institution_id','patient_id','purpose','channel','id'))
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    purpose = db.Column(db.String(30), nullable=False)
    channel = db.Column(db.String(20), nullable=False)
    scope = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    destination = db.Column(db.String(254), nullable=False, default='')
    verified_at = db.Column(db.DateTime)
    verified_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    contact_start = db.Column(db.Time)
    contact_end = db.Column(db.Time)
    timezone = db.Column(db.String(80), nullable=False)
    method = db.Column(db.String(80), nullable=False)
    notice_version = db.Column(db.String(120), nullable=False)
    recorded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recorded_at = db.Column(db.DateTime, nullable=False, default=now)


class CareReview(db.Model):
    __tablename__ = 'care_plan_reviews'
    __table_args__ = (db.UniqueConstraint('plan_id','sequence'),
        db.ForeignKeyConstraint(['plan_id','patient_id'],['care_plans.id','care_plans.patient_id'],name='review_plan_patient_match'),
        db.CheckConstraint("status IN ('pending','completed','superseded','cancelled')"),
        db.Index('one_pending_care_review','plan_id',unique=True,
            sqlite_where=db.text("status = 'pending'"),postgresql_where=db.text("status = 'pending'")))
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('care_plans.id'), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    cover_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    due_at = db.Column(db.DateTime)
    interval_days = db.Column(db.Integer)
    policy_id = db.Column(db.Integer, db.ForeignKey('coordination_policies.id'))
    status = db.Column(db.String(20), nullable=False, default='pending')
    reviewed_at = db.Column(db.DateTime)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    next_review_at = db.Column(db.DateTime)
    escalated = db.Column(db.Boolean, nullable=False, default=False)
    owner_unavailable = db.Column(db.Boolean, nullable=False, default=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    updated_at = db.Column(db.DateTime, nullable=False, default=now)


class CareReviewSignoff(db.Model):
    __tablename__ = 'care_review_signoffs'
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('care_plan_reviews.id'), nullable=False, unique=True)
    outcome = db.Column(db.Text, nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewed_at = db.Column(db.DateTime, nullable=False)


class CoordinationHistory(db.Model):
    """Operational history uses enumerated actions and metadata; clinical text is separate."""
    __tablename__ = 'coordination_history'
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    source_type = db.Column(db.String(30), nullable=False)
    source_id = db.Column(db.Integer, nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(40), nullable=False)
    previous_owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    previous_cover_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    cover_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    outcome_code = db.Column(db.String(50), nullable=False, default='')
    created_at = db.Column(db.DateTime, nullable=False, default=now)
