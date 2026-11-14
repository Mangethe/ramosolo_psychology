-- 001: NEW database baseline only. Review before applying to Supabase.
BEGIN;
CREATE SCHEMA IF NOT EXISTS lesonto;
SET LOCAL search_path TO lesonto, public;


CREATE TABLE institutions (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	address VARCHAR(350), 
	PRIMARY KEY (id), 
	CHECK (kind in ('medical', 'education'))
)

;


CREATE TABLE users (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	session_version INTEGER NOT NULL, 
	failed_logins INTEGER NOT NULL, 
	locked_until TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (email)
)

;


CREATE TABLE audit_events (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	actor_id INTEGER NOT NULL, 
	action VARCHAR(80) NOT NULL, 
	resource_type VARCHAR(40) NOT NULL, 
	resource_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
)

;


CREATE TABLE booking_requests (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	phone VARCHAR(40) NOT NULL, 
	service VARCHAR(100) NOT NULL, 
	preferred_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	consent_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id)
)

;


CREATE TABLE memberships (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	institution_id INTEGER NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	supervising_doctor_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (user_id, institution_id), 
	CHECK (role in ('dr','nurse','admin','dr_assist','patient')), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(supervising_doctor_id) REFERENCES users (id)
)

;


CREATE TABLE patients (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	user_id INTEGER, 
	doctor_id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	email VARCHAR(254), 
	phone VARCHAR(40), 
	PRIMARY KEY (id), 
	UNIQUE (institution_id, user_id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(doctor_id) REFERENCES users (id)
)

;


CREATE TABLE admissions (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	facility VARCHAR(120) NOT NULL, 
	admitted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	discharged_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	CHECK (discharged_at is null or discharged_at >= admitted_at), 
	FOREIGN KEY(patient_id) REFERENCES patients (id)
)

;


CREATE TABLE appointments (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	starts_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	service VARCHAR(100) NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (status in ('scheduled','completed','cancelled','no_show')), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(doctor_id) REFERENCES users (id)
)

;


CREATE TABLE care_assignments (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	nurse_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (patient_id, nurse_id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(nurse_id) REFERENCES users (id)
)

;

CREATE INDEX ix_admissions_patient_id ON admissions (patient_id);

CREATE UNIQUE INDEX one_open_admission ON admissions (patient_id) WHERE discharged_at IS NULL;

CREATE INDEX ix_appointments_patient_id ON appointments (patient_id);

CREATE INDEX ix_appointments_starts_at ON appointments (starts_at);

CREATE UNIQUE INDEX one_doctor_slot ON appointments (doctor_id, starts_at) WHERE status != 'cancelled';

CREATE UNIQUE INDEX one_patient_slot ON appointments (patient_id, starts_at) WHERE status != 'cancelled';

-- Keep medical and account tables outside the public Data API schema.
REVOKE ALL ON SCHEMA lesonto FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL TABLES IN SCHEMA lesonto FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA lesonto FROM PUBLIC, anon, authenticated;
CREATE TABLE lesonto.schema_versions (version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
INSERT INTO lesonto.schema_versions (version) VALUES (1);
COMMIT;
