-- 007: Forward-only private-schema bridge for the existing ramosolo v6 ledger.
-- Do not apply legacy 002/003 to this schema. No base booking, financial or provenance table is replaced.
BEGIN;
SET LOCAL search_path TO ramosolo, public;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '5min';
SELECT pg_advisory_xact_lock(hashtext('ramosolo_coordination_migrations'));
DO $$ BEGIN
 IF to_regclass('ramosolo.schema_versions') IS NULL THEN RAISE EXCEPTION 'Expected existing ramosolo schema'; END IF;
 IF (SELECT array_agg(version ORDER BY version) FROM schema_versions) IS DISTINCT FROM ARRAY[1,2,3,4,5,6] THEN RAISE EXCEPTION 'Expected ramosolo version 6; review migration ordering'; END IF;
END $$;


CREATE TABLE care_plans (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	author_id INTEGER NOT NULL, 
	owner_id INTEGER NOT NULL, 
	goals TEXT NOT NULL, 
	warning_signs TEXT NOT NULL, 
	channels JSON NOT NULL, 
	communication_consent BOOLEAN NOT NULL, 
	planned_appointments TEXT NOT NULL, 
	review_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	response_steps TEXT NOT NULL, 
	urgent_help TEXT NOT NULL, 
	monitoring_hours VARCHAR(500) NOT NULL, 
	rules JSON NOT NULL, 
	clinical_definitions TEXT NOT NULL, 
	patient_visible BOOLEAN NOT NULL, 
	agreed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT care_plan_patient_identity UNIQUE (id, patient_id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(author_id) REFERENCES users (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE INDEX ix_care_plans_patient_id ON care_plans (patient_id);

CREATE TABLE patient_permissions (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	membership_id INTEGER NOT NULL, 
	permission VARCHAR(40) NOT NULL, 
	approved_by_id INTEGER NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (patient_id, membership_id, permission), 
	CHECK (permission IN ('care_plan','clinical_events','patient_concerns','diagnoses','clinical_notes','psychotherapy_notes','observations','external_practitioners','export')), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(membership_id) REFERENCES memberships (id), 
	FOREIGN KEY(approved_by_id) REFERENCES users (id)
);

CREATE INDEX ix_patient_permissions_patient_id ON patient_permissions (patient_id);

CREATE TABLE clinical_records (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	author_id INTEGER NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	content TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (kind IN ('diagnoses','clinical_notes','psychotherapy_notes')), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(author_id) REFERENCES users (id)
);

CREATE INDEX ix_clinical_records_patient_id ON clinical_records (patient_id);

CREATE TABLE nursing_observations (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	author_id INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	concern_escalated BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(author_id) REFERENCES users (id)
);

CREATE INDEX ix_nursing_observations_patient_id ON nursing_observations (patient_id);

CREATE TABLE external_practitioners (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	registration_reference VARCHAR(120) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	phone VARCHAR(40) NOT NULL, 
	author_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(author_id) REFERENCES users (id)
);

CREATE INDEX ix_external_practitioners_patient_id ON external_practitioners (patient_id);

CREATE TABLE patient_preferences (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	channels JSON NOT NULL, 
	communication_consent BOOLEAN NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (patient_id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id)
);

CREATE TABLE continuity_events (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	author_id INTEGER NOT NULL, 
	owner_id INTEGER NOT NULL, 
	category VARCHAR(30) NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	source_key VARCHAR(100) NOT NULL, 
	appointment_id INTEGER, 
	reason TEXT NOT NULL, 
	definition TEXT NOT NULL, 
	due_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	state VARCHAR(20) NOT NULL, 
	PRIMARY KEY (id), 
	CHECK ((category = 'administrative' AND kind IN ('missed_appointment','unconfirmed_booking','failed_reminder','overdue_followup')) OR (category = 'patient_reported' AND kind IN ('contact_request','check_in')) OR (category = 'clinical' AND kind IN ('deterioration','lapse','relapse'))), 
	CHECK (state IN ('open','acknowledged','escalated','closed','archived')), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(plan_id) REFERENCES care_plans (id), 
	FOREIGN KEY(author_id) REFERENCES users (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id), 
	FOREIGN KEY(appointment_id) REFERENCES appointments (id)
);

CREATE INDEX ix_continuity_events_patient_id ON continuity_events (patient_id);

CREATE UNIQUE INDEX one_live_continuity_event ON continuity_events (patient_id, kind, source_key) WHERE state NOT IN ('closed','archived');

CREATE TABLE continuity_history (
	id SERIAL NOT NULL, 
	event_id INTEGER NOT NULL, 
	actor_id INTEGER NOT NULL, 
	action VARCHAR(40) NOT NULL, 
	detail TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(event_id) REFERENCES continuity_events (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE INDEX ix_continuity_history_event_id ON continuity_history (event_id);

CREATE TABLE continuity_notifications (
	id SERIAL NOT NULL, 
	event_id INTEGER NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	mode VARCHAR(20) NOT NULL, 
	body VARCHAR(250) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (event_id, channel), 
	CHECK (mode = 'sandbox'), 
	FOREIGN KEY(event_id) REFERENCES continuity_events (id)
);

REVOKE ALL ON care_plans, patient_permissions, clinical_records, nursing_observations, external_practitioners, patient_preferences, continuity_events, continuity_history, continuity_notifications FROM PUBLIC, anon, authenticated;

REVOKE ALL ON SEQUENCE care_plans_id_seq, patient_permissions_id_seq, clinical_records_id_seq, nursing_observations_id_seq, external_practitioners_id_seq, patient_preferences_id_seq, continuity_events_id_seq, continuity_history_id_seq, continuity_notifications_id_seq FROM PUBLIC, anon, authenticated;

INSERT INTO schema_versions(version) VALUES (7);

COMMIT;
