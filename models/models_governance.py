from datetime import datetime, timezone
from extensions import db


class AuditEvent(db.Model):
    __tablename__ = 'audit_events'
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(80), nullable=False)
    resource_type = db.Column(db.String(40), nullable=False)
    resource_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
