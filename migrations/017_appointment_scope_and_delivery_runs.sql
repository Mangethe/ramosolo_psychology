-- Additive candidate. Existing attachment, booking, payment and outbox triggers are retained.
BEGIN;
SET LOCAL lock_timeout = '5s';
ALTER TABLE ramosolo.patients ADD CONSTRAINT patient_institution_identity UNIQUE (id, institution_id);
ALTER TABLE ramosolo.appointments ADD CONSTRAINT appointment_patient_institution_fkey
    FOREIGN KEY (patient_id, institution_id) REFERENCES ramosolo.patients(id, institution_id) NOT VALID;
ALTER TABLE ramosolo.appointments VALIDATE CONSTRAINT appointment_patient_institution_fkey;
-- On the observed hosted shape, appointments can belong directly to a booking request.
DO $scope$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='ramosolo'
        AND table_name='appointments' AND column_name='booking_request_id') THEN
        ALTER TABLE ramosolo.booking_requests ADD CONSTRAINT booking_request_institution_identity
            UNIQUE (id, institution_id);
        ALTER TABLE ramosolo.appointments ADD CONSTRAINT appointment_request_institution_fkey
            FOREIGN KEY (booking_request_id,institution_id) REFERENCES ramosolo.booking_requests(id,institution_id)
            NOT VALID;
        ALTER TABLE ramosolo.appointments VALIDATE CONSTRAINT appointment_request_institution_fkey;
    END IF;
END;
$scope$;
CREATE INDEX ix_patients_institution_doctor ON ramosolo.patients (institution_id, doctor_id);
CREATE INDEX ix_care_assignments_nurse_patient ON ramosolo.care_assignments (nurse_id, patient_id);
CREATE TABLE ramosolo.email_delivery_runs (
    id varchar(32) PRIMARY KEY,
    mode varchar(12) NOT NULL CHECK (mode IN ('fake','live')),
    state varchar(16) NOT NULL CHECK (state IN ('running','completed','failed','interrupted')),
    started_at bigint NOT NULL,
    lease_until bigint NOT NULL,
    finished_at bigint,
    counts jsonb NOT NULL
);
CREATE INDEX ix_email_delivery_runs_recovery ON ramosolo.email_delivery_runs (state, lease_until);
ALTER TABLE ramosolo.email_delivery_runs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ramosolo.email_delivery_runs FROM PUBLIC, anon, authenticated;
ALTER TABLE ramosolo.security_emails ADD COLUMN last_run_id varchar(32) REFERENCES ramosolo.email_delivery_runs(id);
ALTER TABLE ramosolo.security_emails ADD COLUMN result_code varchar(40);
CREATE INDEX ix_security_emails_last_run_id ON ramosolo.security_emails (last_run_id);
COMMIT;
