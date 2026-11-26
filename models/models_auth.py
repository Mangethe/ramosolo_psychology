from extensions import db


class PortalSession(db.Model):
    __tablename__ = 'portal_sessions'
    token_hash = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    account_version = db.Column(db.Integer, nullable=False)
    privileges = db.Column(db.String(64), nullable=False)
    started_at = db.Column(db.BigInteger, nullable=False)
    last_seen_at = db.Column(db.BigInteger, nullable=False)
    idle_expires_at = db.Column(db.BigInteger, nullable=False, index=True)
    absolute_expires_at = db.Column(db.BigInteger, nullable=False, index=True)
    mfa_at = db.Column(db.BigInteger)
    mfa_method = db.Column(db.String(12))


class AccountVerification(db.Model):
    __tablename__ = 'account_verifications'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    verified_email = db.Column(db.String(254))
    verified_at = db.Column(db.BigInteger)
    requested_email = db.Column(db.String(254))
    verification_id = db.Column(db.String(43), unique=True)
    token_hash = db.Column(db.String(64))
    expires_at = db.Column(db.BigInteger)
    resend_after = db.Column(db.BigInteger, nullable=False, default=0)
    window_started_at = db.Column(db.BigInteger, nullable=False, default=0)
    send_count = db.Column(db.Integer, nullable=False, default=0)
    mfa_reenroll_required = db.Column(db.Boolean, nullable=False, default=False)


class AccountRecovery(db.Model):
    __tablename__ = 'account_recoveries'
    __table_args__ = (db.CheckConstraint('requestor_id <> approver_id AND user_id <> requestor_id AND user_id <> approver_id'),)
    ticket = db.Column(db.String(64), primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    requestor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    started_at = db.Column(db.BigInteger, nullable=False)


class EmailDeliveryRun(db.Model):
    __tablename__ = 'email_delivery_runs'
    __table_args__ = (
        db.CheckConstraint("mode IN ('fake','live')"),
        db.CheckConstraint("state IN ('running','completed','failed','interrupted')"),
        db.Index('ix_email_delivery_runs_recovery', 'state', 'lease_until'),
    )
    id = db.Column(db.String(32), primary_key=True)
    mode = db.Column(db.String(12), nullable=False)
    state = db.Column(db.String(16), nullable=False)
    started_at = db.Column(db.BigInteger, nullable=False)
    lease_until = db.Column(db.BigInteger, nullable=False)
    finished_at = db.Column(db.BigInteger)
    counts = db.Column(db.JSON, nullable=False)


class SecurityEmail(db.Model):
    __tablename__ = 'security_emails'
    __table_args__ = (db.Index('ix_security_emails_due', 'state', 'next_attempt_at'),)
    dedupe_key = db.Column(db.String(96), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), index=True)
    recipient = db.Column(db.String(254), nullable=False)
    kind = db.Column(db.String(24), nullable=False)
    detail = db.Column(db.String(100))
    created_at = db.Column(db.BigInteger, nullable=False)
    next_attempt_at = db.Column(db.BigInteger, nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    state = db.Column(db.String(16), nullable=False, default='pending')
    last_run_id = db.Column(db.String(32), db.ForeignKey('email_delivery_runs.id'), index=True)
    result_code = db.Column(db.String(40))


class AppointmentEmail(db.Model):
    __tablename__ = 'appointment_emails'
    dedupe_key = db.Column(db.String(96), db.ForeignKey('security_emails.dedupe_key', ondelete='CASCADE'), primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id', ondelete='CASCADE'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    schedule_version = db.Column(db.Integer, nullable=False)
    scheduled_start = db.Column(db.DateTime, nullable=False)
    decision_id = db.Column(db.Integer, db.ForeignKey('communication_decisions.id'), nullable=False)
    lead_minutes = db.Column(db.Integer)


class DeliveryLimit(db.Model):
    __tablename__ = 'delivery_limits'
    key = db.Column(db.String(100), primary_key=True)
    expires_at = db.Column(db.BigInteger, nullable=False, index=True)
    count = db.Column(db.Integer, nullable=False)


class VerifiedPhone(db.Model):
    __tablename__ = 'verified_phones'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    encrypted_number = db.Column(db.LargeBinary, nullable=False)
    verified_at = db.Column(db.BigInteger, nullable=False)


class PhoneChallenge(db.Model):
    __tablename__ = 'phone_challenges'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    challenge_id = db.Column(db.String(43), nullable=False, unique=True)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    session_hash = db.Column(db.String(64), nullable=False)
    purpose = db.Column(db.String(24), nullable=False)
    encrypted_number = db.Column(db.LargeBinary, nullable=False)
    destination_key = db.Column(db.String(64), nullable=False)
    reference = db.Column(db.String(64))
    provider = db.Column(db.String(16), nullable=False)
    state = db.Column(db.String(16), nullable=False)
    expires_at = db.Column(db.BigInteger, nullable=False, index=True)
    resend_after = db.Column(db.BigInteger, nullable=False)
    sends = db.Column(db.Integer, nullable=False)
    attempts = db.Column(db.Integer, nullable=False)


class Authenticator(db.Model):
    __tablename__ = 'authenticators'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    encrypted_secret = db.Column(db.LargeBinary, nullable=False)
    last_counter = db.Column(db.BigInteger, nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    blocked_until = db.Column(db.BigInteger, nullable=False, default=0)


class RecoveryCode(db.Model):
    __tablename__ = 'auth_recovery_codes'
    user_id = db.Column(db.Integer, db.ForeignKey('authenticators.user_id', ondelete='CASCADE'), primary_key=True)
    code_hash = db.Column(db.String(64), primary_key=True)


class PendingAuthentication(db.Model):
    __tablename__ = 'pending_authentications'
    token_hash = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    account_version = db.Column(db.Integer, nullable=False)
    privileges = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.BigInteger, nullable=False, index=True)
    mode = db.Column(db.String(16), nullable=False)
    encrypted_secret = db.Column(db.LargeBinary)
    attempts = db.Column(db.Integer, nullable=False, default=0)


class FederatedIdentity(db.Model):
    __tablename__ = 'federated_identities'
    __table_args__ = (db.UniqueConstraint('issuer', 'user_id'),)
    issuer = db.Column(db.String(350), primary_key=True)
    subject = db.Column(db.String(255), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)


class OIDCExchange(db.Model):
    __tablename__ = 'oidc_exchanges'
    token_hash = db.Column(db.String(64), primary_key=True)
    expires_at = db.Column(db.BigInteger, nullable=False, index=True)
    session_hash = db.Column(db.String(64))
    code_verifier = db.Column(db.String(128))
    nonce = db.Column(db.String(128))
    issuer = db.Column(db.String(350), nullable=False)
    subject = db.Column(db.String(255))
