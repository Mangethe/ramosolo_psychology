from datetime import datetime, timezone
from extensions import db


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PatientPermission(db.Model):
    """Explicit, revocable, clinician-issued access; never inferred from admin status."""
    __tablename__ = 'patient_permissions'
    __table_args__ = (db.UniqueConstraint('patient_id', 'membership_id', 'permission'),
        db.CheckConstraint("permission IN ('care_plan','clinical_events','patient_concerns','diagnoses','clinical_notes','psychotherapy_notes','observations','external_practitioners','export')"))
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, index=True)
    membership_id = db.Column(db.Integer, db.ForeignKey('memberships.id'), nullable=False)
    permission = db.Column(db.String(40), nullable=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now)


class ClinicalRecord(db.Model):
    __tablename__ = 'clinical_records'
    __table_args__ = (db.CheckConstraint("kind IN ('diagnoses','clinical_notes','psychotherapy_notes')"),)
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    kind = db.Column(db.String(40), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)


class NursingObservation(db.Model):
    """An observation is never a clinician-confirmed finding or diagnosis."""
    __tablename__ = 'nursing_observations'
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    concern_escalated = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)


class ExternalPractitioner(db.Model):
    """Patient's referenced external treating psychiatrist. No account or membership link."""
    __tablename__ = 'external_practitioners'
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    registration_reference = db.Column(db.String(120), nullable=False, default='')
    email = db.Column(db.String(254), nullable=False, default='')
    phone = db.Column(db.String(40), nullable=False, default='')
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)


class PatientPreference(db.Model):
    __tablename__ = 'patient_preferences'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, unique=True)
    channels = db.Column(db.JSON, nullable=False)
    communication_consent = db.Column(db.Boolean, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=now)
