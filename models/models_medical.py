from extensions import db


class Patient(db.Model):
    __tablename__ = 'patients'
    __table_args__ = (db.UniqueConstraint('institution_id', 'user_id'),
        db.UniqueConstraint('id', 'institution_id', name='patient_institution_identity'),
        db.Index('ix_patients_institution_doctor', 'institution_id', 'doctor_id'))
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), default='')
    phone = db.Column(db.String(40), default='')
    doctor = db.relationship('User', foreign_keys=[doctor_id])


class CareAssignment(db.Model):
    __tablename__ = 'care_assignments'
    __table_args__ = (db.UniqueConstraint('patient_id', 'nurse_id'),
        db.Index('ix_care_assignments_nurse_patient', 'nurse_id', 'patient_id'))
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    nurse_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)


class Appointment(db.Model):
    __tablename__ = 'appointments'
    __table_args__ = (db.CheckConstraint("status in ('scheduled','held','expired','completed','cancelled','no_show')"),
        db.ForeignKeyConstraint(['patient_id', 'institution_id'], ['patients.id', 'patients.institution_id'],
                                name='appointment_patient_institution_fkey'),
        db.Index('one_patient_slot', 'patient_id', 'starts_at', unique=True, sqlite_where=db.text("status != 'cancelled'"), postgresql_where=db.text("status != 'cancelled'")),
        db.Index('one_doctor_slot', 'doctor_id', 'starts_at', unique=True, sqlite_where=db.text("status != 'cancelled'"), postgresql_where=db.text("status != 'cancelled'")))
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    starts_at = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default='scheduled')
    service = db.Column(db.String(100), nullable=False)
    ends_at = db.Column(db.DateTime)
    occupied_until = db.Column(db.DateTime)
    care_type = db.Column(db.String(20))
    visit_kind = db.Column(db.String(20))
    schedule_version = db.Column(db.Integer, nullable=False, default=1)
    hold_expires_at = db.Column(db.DateTime)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'))
    patient = db.relationship('Patient', foreign_keys=[patient_id])


class Admission(db.Model):
    __tablename__ = 'admissions'
    __table_args__ = (db.UniqueConstraint('id','patient_id',name='admission_patient_identity'),
        db.CheckConstraint('discharged_at is null or discharged_at >= admitted_at'),
        db.Index('one_open_admission', 'patient_id', unique=True, sqlite_where=db.text('discharged_at IS NULL'), postgresql_where=db.text('discharged_at IS NULL')))
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, index=True)
    facility = db.Column(db.String(120), nullable=False)
    admitted_at = db.Column(db.DateTime, nullable=False)
    discharged_at = db.Column(db.DateTime)
    patient = db.relationship('Patient')


class BookingRequest(db.Model):
    __tablename__ = 'booking_requests'
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    service = db.Column(db.String(100), nullable=False)
    preferred_at = db.Column(db.DateTime, nullable=False)
    consent_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
