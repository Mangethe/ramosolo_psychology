-- Add delivery context and quota reservations without modifying existing jobs.
BEGIN;
SET LOCAL lock_timeout = '5s';
ALTER TABLE ramosolo.security_emails ALTER COLUMN user_id DROP NOT NULL;
CREATE TABLE ramosolo.appointment_emails (
    dedupe_key varchar(96) PRIMARY KEY REFERENCES ramosolo.security_emails(dedupe_key) ON DELETE CASCADE,
    institution_id integer NOT NULL REFERENCES ramosolo.institutions(id),
    appointment_id integer NOT NULL REFERENCES ramosolo.appointments(id) ON DELETE CASCADE,
    patient_id integer NOT NULL REFERENCES ramosolo.patients(id),
    schedule_version integer NOT NULL,
    scheduled_start timestamp NOT NULL,
    decision_id integer NOT NULL REFERENCES ramosolo.communication_decisions(id),
    lead_minutes integer
);
CREATE INDEX ix_appointment_emails_appointment_id ON ramosolo.appointment_emails (appointment_id);
CREATE TABLE ramosolo.delivery_limits (
    key varchar(100) PRIMARY KEY,
    expires_at bigint NOT NULL,
    count integer NOT NULL
);
CREATE INDEX ix_delivery_limits_expires_at ON ramosolo.delivery_limits (expires_at);
ALTER TABLE ramosolo.appointment_emails ENABLE ROW LEVEL SECURITY;
ALTER TABLE ramosolo.delivery_limits ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ramosolo.appointment_emails, ramosolo.delivery_limits FROM PUBLIC, anon, authenticated;
COMMIT;
