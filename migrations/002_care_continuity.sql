-- 002: Care continuity. Review in an isolated database before applying.

-- Matches baseline schema lesonto; change search_path explicitly for a different private schema.

BEGIN;

SET LOCAL search_path TO lesonto, public;

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
	agreed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(author_id) REFERENCES users (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE INDEX ix_care_plans_patient_id ON care_plans (patient_id);

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

REVOKE ALL ON care_plans, continuity_events, continuity_history, continuity_notifications FROM PUBLIC, anon, authenticated;

REVOKE ALL ON SEQUENCE care_plans_id_seq, continuity_events_id_seq, continuity_history_id_seq, continuity_notifications_id_seq FROM PUBLIC, anon, authenticated;

INSERT INTO schema_versions (version) VALUES (2);

COMMIT;
