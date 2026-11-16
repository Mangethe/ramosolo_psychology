-- 003: Explicit patient permissions, clinical record boundaries and practitioner references.

-- Review after 001 and 002; adapt private schema search_path when needed.

BEGIN;

SET LOCAL search_path TO lesonto, public;

ALTER TABLE care_plans ADD COLUMN patient_visible BOOLEAN NOT NULL DEFAULT false;

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

REVOKE ALL ON patient_permissions, clinical_records, nursing_observations, external_practitioners, patient_preferences FROM PUBLIC, anon, authenticated;

REVOKE ALL ON SEQUENCE patient_permissions_id_seq, clinical_records_id_seq, nursing_observations_id_seq, external_practitioners_id_seq, patient_preferences_id_seq FROM PUBLIC, anon, authenticated;

-- Existing nursing assignments receive NO automatic clinical grants.

-- Existing plans remain unpublished to patients until a clinician approves a new version.

INSERT INTO schema_versions (version) VALUES (3);

COMMIT;
