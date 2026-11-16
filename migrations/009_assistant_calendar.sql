-- 009: Assistant calendar workflow. Local proposal; requires approved 007/008 first.
BEGIN;
SET LOCAL search_path TO ramosolo, public;
SET LOCAL lock_timeout = '5s';
SELECT pg_advisory_xact_lock(hashtext('ramosolo_coordination_migrations'));
DO $$ BEGIN
 IF (SELECT array_agg(version ORDER BY version) FROM schema_versions) IS DISTINCT FROM ARRAY[1,2,3,4,5,6,7,8] THEN RAISE EXCEPTION 'Expected version 8'; END IF;
END $$;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS ends_at timestamp;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS occupied_until timestamp;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS care_type varchar(20);
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS visit_kind varchar(20);
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS schedule_version integer NOT NULL DEFAULT 1;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS hold_expires_at timestamp;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS institution_id integer REFERENCES institutions(id);

CREATE TABLE IF NOT EXISTS availability_policies (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	daily_limit INTEGER NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	holidays_confirmed BOOLEAN NOT NULL, 
	horizon_days INTEGER NOT NULL, 
	hold_minutes INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (institution_id, doctor_id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(doctor_id) REFERENCES users (id)
)

;

CREATE TABLE IF NOT EXISTS availability_sessions (
	id SERIAL NOT NULL, 
	policy_id INTEGER NOT NULL, 
	weekday INTEGER NOT NULL, 
	care_type VARCHAR(20) NOT NULL, 
	opens_at TIME WITHOUT TIME ZONE NOT NULL, 
	closes_at TIME WITHOUT TIME ZONE NOT NULL, 
	duration_minutes INTEGER NOT NULL, 
	first_minutes INTEGER NOT NULL, 
	assessment_minutes INTEGER NOT NULL, 
	break_minutes INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK ((care_type='outpatient' AND weekday=2) OR (care_type='inpatient' AND weekday IN (0,1,2,4))), 
	CHECK (opens_at < closes_at AND first_minutes BETWEEN 60 AND 120 AND assessment_minutes BETWEEN 1 AND 240 AND break_minutes BETWEEN 5 AND 10), 
	CHECK ((care_type='outpatient' AND duration_minutes BETWEEN 30 AND 60) OR (care_type='inpatient' AND duration_minutes BETWEEN 20 AND 30)), 
	FOREIGN KEY(policy_id) REFERENCES availability_policies (id)
)

;

CREATE TABLE IF NOT EXISTS availability_exceptions (
	id SERIAL NOT NULL, 
	policy_id INTEGER NOT NULL, 
	day DATE NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	care_type VARCHAR(20), 
	opens_at TIME WITHOUT TIME ZONE, 
	closes_at TIME WITHOUT TIME ZONE, 
	duration_minutes INTEGER, 
	first_minutes INTEGER, 
	assessment_minutes INTEGER, 
	break_minutes INTEGER, 
	override_closure BOOLEAN NOT NULL, 
	approved_by INTEGER NOT NULL, 
	reason VARCHAR(240) NOT NULL, 
	approved_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(policy_id) REFERENCES availability_policies (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id)
)

;

CREATE TABLE IF NOT EXISTS public_holidays (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	day DATE NOT NULL, 
	label VARCHAR(120) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id)
)

;

CREATE TABLE IF NOT EXISTS calendar_blocks (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	starts_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	ends_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	reason VARCHAR(30) NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	released_by INTEGER, 
	released_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(doctor_id) REFERENCES users (id), 
	FOREIGN KEY(released_by) REFERENCES users (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;

CREATE TABLE IF NOT EXISTS calendar_delegations (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	assistant_id INTEGER NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (institution_id, doctor_id, assistant_id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(doctor_id) REFERENCES users (id), 
	FOREIGN KEY(assistant_id) REFERENCES users (id)
)

;
ALTER TABLE calendar_delegations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON calendar_delegations FROM PUBLIC, anon, authenticated;
REVOKE ALL ON SEQUENCE calendar_delegations_id_seq FROM PUBLIC, anon, authenticated;

CREATE TABLE IF NOT EXISTS appointment_proposals (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	appointment_id INTEGER NOT NULL, 
	actor_id INTEGER NOT NULL, 
	base_version INTEGER NOT NULL, 
	original_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	proposed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	reason VARCHAR(240) NOT NULL, 
	state VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	responded_at TIMESTAMP WITHOUT TIME ZONE, 
	token_digest VARCHAR(64) NOT NULL, 
	code_digest VARCHAR(64) NOT NULL, 
	communication_decision_id INTEGER, 
	verification_attempts INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (state IN ('pending','accepted','declined','expired','superseded')), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(appointment_id) REFERENCES appointments (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id), 
	UNIQUE (token_digest), 
	FOREIGN KEY(communication_decision_id) REFERENCES communication_decisions (id)
)

;
CREATE UNIQUE INDEX IF NOT EXISTS one_pending_appointment_proposal ON appointment_proposals (appointment_id) WHERE state='pending';
ALTER TABLE appointment_proposals ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON appointment_proposals FROM PUBLIC, anon, authenticated;
REVOKE ALL ON SEQUENCE appointment_proposals_id_seq FROM PUBLIC, anon, authenticated;

CREATE TABLE IF NOT EXISTS calendar_history (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	appointment_id INTEGER, 
	block_id INTEGER, 
	proposal_id INTEGER, 
	actor_id INTEGER, 
	action VARCHAR(40) NOT NULL, 
	original_at TIMESTAMP WITHOUT TIME ZONE, 
	new_at TIMESTAMP WITHOUT TIME ZONE, 
	reason VARCHAR(240) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(appointment_id) REFERENCES appointments (id), 
	FOREIGN KEY(block_id) REFERENCES calendar_blocks (id), 
	FOREIGN KEY(proposal_id) REFERENCES appointment_proposals (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
)

;
ALTER TABLE calendar_history ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON calendar_history FROM PUBLIC, anon, authenticated;
REVOKE ALL ON SEQUENCE calendar_history_id_seq FROM PUBLIC, anon, authenticated;
INSERT INTO schema_versions(version) VALUES (9);
COMMIT;
