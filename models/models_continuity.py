from extensions import db
from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CarePlan(db.Model):
    """Append-only clinician-authored versions; no invented practice defaults."""
    __tablename__ = 'care_plans'
    __table_args__ = (db.UniqueConstraint('id','patient_id',name='care_plan_patient_identity'),)
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    goals = db.Column(db.Text, nullable=False)
    warning_signs = db.Column(db.Text, nullable=False)
    channels = db.Column(db.JSON, nullable=False)
    communication_consent = db.Column(db.Boolean, nullable=False)
    planned_appointments = db.Column(db.Text, nullable=False)
    review_at = db.Column(db.DateTime, nullable=False)
    response_steps = db.Column(db.Text, nullable=False)
    urgent_help = db.Column(db.Text, nullable=False)
    monitoring_hours = db.Column(db.String(500), nullable=False)
    rules = db.Column(db.JSON, nullable=False)
    clinical_definitions = db.Column(db.Text, nullable=False)
    patient_visible = db.Column(db.Boolean, nullable=False, default=False)
    agreed_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    patient = db.relationship('Patient')
    owner = db.relationship('User', foreign_keys=[owner_id])


class ContinuityEvent(db.Model):
    __tablename__ = 'continuity_events'
    __table_args__ = (
        db.CheckConstraint("(category = 'administrative' AND kind IN ('missed_appointment','unconfirmed_booking','failed_reminder','overdue_followup')) OR (category = 'patient_reported' AND kind IN ('contact_request','check_in')) OR (category = 'clinical' AND kind IN ('deterioration','lapse','relapse'))"),
        db.CheckConstraint("state IN ('open','acknowledged','escalated','closed','archived')"),
        db.Index('one_live_continuity_event', 'patient_id', 'kind', 'source_key', unique=True,
                 sqlite_where=db.text("state NOT IN ('closed','archived')"),
                 postgresql_where=db.text("state NOT IN ('closed','archived')")),
    )
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('care_plans.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category = db.Column(db.String(30), nullable=False)
    kind = db.Column(db.String(40), nullable=False)
    source_key = db.Column(db.String(100), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'))
    reason = db.Column(db.Text, nullable=False)
    definition = db.Column(db.Text, nullable=False, default='')
    due_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    state = db.Column(db.String(20), nullable=False, default='open')
    patient = db.relationship('Patient')
    plan = db.relationship('CarePlan')
    owner = db.relationship('User', foreign_keys=[owner_id])
    history = db.relationship('ContinuityHistory', order_by='ContinuityHistory.id')


class ContinuityHistory(db.Model):
    __tablename__ = 'continuity_history'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('continuity_events.id'), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(40), nullable=False)
    detail = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class ContinuityNotification(db.Model):
    """Sandbox previews only. This model has deliberately no delivery adapter."""
    __tablename__ = 'continuity_notifications'
    __table_args__ = (db.UniqueConstraint('event_id', 'channel'),
                      db.CheckConstraint("mode = 'sandbox'"))
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('continuity_events.id'), nullable=False)
    channel = db.Column(db.String(20), nullable=False)
    mode = db.Column(db.String(20), nullable=False, default='sandbox')
    body = db.Column(db.String(250), nullable=False)
    purpose = db.Column(db.String(30), nullable=False, default='administrative_contact')
    scope = db.Column(db.String(200), nullable=False, default='practice')
    state = db.Column(db.String(20), nullable=False, default='queued')
    result_code = db.Column(db.String(80), nullable=False, default='')
    decision_id = db.Column(db.Integer, db.ForeignKey('communication_decisions.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
