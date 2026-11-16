-- 008: Local care coordination; existing outbox is reused, not replaced.
BEGIN;
SET LOCAL search_path TO ramosolo, public;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '5min';
SELECT pg_advisory_xact_lock(hashtext('ramosolo_coordination_migrations'));
DO $$ BEGIN
 IF (SELECT array_agg(version ORDER BY version) FROM schema_versions) IS DISTINCT FROM ARRAY[1,2,3,4,5,6,7] THEN RAISE EXCEPTION 'Expected ramosolo version 7'; END IF;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS admission_patient_identity ON admissions(id,patient_id);
CREATE UNIQUE INDEX IF NOT EXISTS care_plan_patient_identity ON care_plans(id,patient_id);


CREATE TABLE coordination_policies (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	version INTEGER NOT NULL, 
	deadline_hours INTEGER NOT NULL, 
	due_soon_days INTEGER NOT NULL, 
	instructions VARCHAR(1500) NOT NULL, 
	approved_by_id INTEGER NOT NULL, 
	approved_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (institution_id, kind, version), 
	CHECK (kind IN ('discharge','review')), 
	CHECK (deadline_hours > 0 AND due_soon_days >= 0), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(approved_by_id) REFERENCES users (id)
);

CREATE TABLE communication_decisions (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	purpose VARCHAR(30) NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	scope VARCHAR(200) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	destination VARCHAR(254) NOT NULL, 
	verified_at TIMESTAMP WITHOUT TIME ZONE, 
	verified_by_id INTEGER, 
	contact_start TIME WITHOUT TIME ZONE, 
	contact_end TIME WITHOUT TIME ZONE, 
	timezone VARCHAR(80) NOT NULL, 
	method VARCHAR(80) NOT NULL, 
	notice_version VARCHAR(120) NOT NULL, 
	recorded_by_id INTEGER NOT NULL, 
	recorded_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (purpose IN ('reminders','administrative_contact','referral_sharing','care_plan_sharing')), 
	CHECK (channel IN ('portal','phone','email','sms')), 
	CHECK (status IN ('granted','declined','withdrawn')), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(verified_by_id) REFERENCES users (id), 
	FOREIGN KEY(recorded_by_id) REFERENCES users (id)
);

CREATE INDEX communication_decision_lookup ON communication_decisions (institution_id, patient_id, purpose, channel, id);

CREATE TABLE discharge_followups (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	admission_id INTEGER NOT NULL, 
	owner_id INTEGER, 
	cover_id INTEGER, 
	team VARCHAR(120) NOT NULL, 
	due_at TIMESTAMP WITHOUT TIME ZONE, 
	policy_id INTEGER, 
	planning_complete BOOLEAN NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	outcome VARCHAR(1500) NOT NULL, 
	closure_reason VARCHAR(1000) NOT NULL, 
	escalated BOOLEAN NOT NULL, 
	owner_unavailable BOOLEAN NOT NULL, 
	patient_visible BOOLEAN NOT NULL, 
	agreed_action VARCHAR(1000) NOT NULL, 
	version INTEGER NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (admission_id), 
	CONSTRAINT discharge_episode_patient_match FOREIGN KEY(admission_id, patient_id) REFERENCES admissions (id, patient_id), 
	CHECK (status IN ('open','contacted','completed','cancelled')), 
	CHECK (NOT planning_complete OR (owner_id IS NOT NULL AND due_at IS NOT NULL AND policy_id IS NOT NULL)), 
	CHECK (status <> 'completed' OR (outcome <> '' AND closure_reason <> '')), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(admission_id) REFERENCES admissions (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id), 
	FOREIGN KEY(cover_id) REFERENCES users (id), 
	FOREIGN KEY(policy_id) REFERENCES coordination_policies (id)
);

CREATE INDEX ix_discharge_followups_patient_id ON discharge_followups (patient_id);

CREATE TABLE care_referrals (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	direction VARCHAR(20) NOT NULL, 
	other_party VARCHAR(200) NOT NULL, 
	practitioner_id INTEGER, 
	referred_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	owner_id INTEGER, 
	cover_id INTEGER, 
	due_at TIMESTAMP WITHOUT TIME ZONE, 
	requested_action VARCHAR(1500) NOT NULL, 
	next_action VARCHAR(1000) NOT NULL, 
	outstanding_information VARCHAR(1000) NOT NULL, 
	consent_id INTEGER, 
	status VARCHAR(30) NOT NULL, 
	response_at TIMESTAMP WITHOUT TIME ZONE, 
	appointment_at TIMESTAMP WITHOUT TIME ZONE, 
	appointment_id INTEGER, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	closure_reason VARCHAR(1000) NOT NULL, 
	owner_unavailable BOOLEAN NOT NULL, 
	escalated BOOLEAN NOT NULL, 
	patient_visible BOOLEAN NOT NULL, 
	submission_key VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (institution_id, patient_id, submission_key), 
	CHECK (direction IN ('incoming','outgoing')), 
	CHECK (status IN ('draft','sent','acknowledged','accepted','appointment_arranged','completed','declined','cancelled')), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(practitioner_id) REFERENCES external_practitioners (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id), 
	FOREIGN KEY(cover_id) REFERENCES users (id), 
	FOREIGN KEY(consent_id) REFERENCES communication_decisions (id), 
	FOREIGN KEY(appointment_id) REFERENCES appointments (id)
);

CREATE INDEX ix_care_referrals_patient_id ON care_referrals (patient_id);

CREATE TABLE referral_clinical_records (
	id SERIAL NOT NULL, 
	referral_id INTEGER NOT NULL, 
	author_id INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(referral_id) REFERENCES care_referrals (id), 
	FOREIGN KEY(author_id) REFERENCES users (id)
);

CREATE INDEX ix_referral_clinical_records_referral_id ON referral_clinical_records (referral_id);

CREATE TABLE care_plan_reviews (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	sequence INTEGER NOT NULL, 
	owner_id INTEGER, 
	cover_id INTEGER, 
	due_at TIMESTAMP WITHOUT TIME ZONE, 
	interval_days INTEGER, 
	policy_id INTEGER, 
	status VARCHAR(20) NOT NULL, 
	reviewed_at TIMESTAMP WITHOUT TIME ZONE, 
	reviewer_id INTEGER, 
	next_review_at TIMESTAMP WITHOUT TIME ZONE, 
	escalated BOOLEAN NOT NULL, 
	owner_unavailable BOOLEAN NOT NULL, 
	version INTEGER NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (plan_id, sequence), 
	CONSTRAINT review_plan_patient_match FOREIGN KEY(plan_id, patient_id) REFERENCES care_plans (id, patient_id), 
	CHECK (status IN ('pending','completed','superseded','cancelled')), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(plan_id) REFERENCES care_plans (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id), 
	FOREIGN KEY(cover_id) REFERENCES users (id), 
	FOREIGN KEY(policy_id) REFERENCES coordination_policies (id), 
	FOREIGN KEY(reviewer_id) REFERENCES users (id)
);

CREATE INDEX ix_care_plan_reviews_patient_id ON care_plan_reviews (patient_id);

CREATE UNIQUE INDEX one_pending_care_review ON care_plan_reviews (plan_id) WHERE status = 'pending';

CREATE TABLE care_review_signoffs (
	id SERIAL NOT NULL, 
	review_id INTEGER NOT NULL, 
	outcome TEXT NOT NULL, 
	reviewer_id INTEGER NOT NULL, 
	reviewed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (review_id), 
	FOREIGN KEY(review_id) REFERENCES care_plan_reviews (id), 
	FOREIGN KEY(reviewer_id) REFERENCES users (id)
);

CREATE TABLE coordination_history (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	source_type VARCHAR(30) NOT NULL, 
	source_id INTEGER NOT NULL, 
	actor_id INTEGER NOT NULL, 
	action VARCHAR(40) NOT NULL, 
	previous_owner_id INTEGER, 
	owner_id INTEGER, 
	previous_cover_id INTEGER, 
	cover_id INTEGER, 
	outcome_code VARCHAR(50) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id), 
	FOREIGN KEY(previous_owner_id) REFERENCES users (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id), 
	FOREIGN KEY(previous_cover_id) REFERENCES users (id), 
	FOREIGN KEY(cover_id) REFERENCES users (id)
);

ALTER TABLE continuity_notifications ADD COLUMN purpose varchar(30) NOT NULL DEFAULT 'administrative_contact';
ALTER TABLE continuity_notifications ADD COLUMN scope varchar(200) NOT NULL DEFAULT 'practice';
-- Historical previews have no purpose-specific consent evidence. Keep history, suppress any delivery eligibility.
ALTER TABLE continuity_notifications ADD COLUMN state varchar(20) NOT NULL DEFAULT 'suppressed';
ALTER TABLE continuity_notifications ALTER COLUMN state SET DEFAULT 'queued';
ALTER TABLE continuity_notifications ADD COLUMN result_code varchar(80) NOT NULL DEFAULT 'legacy_consent_unverified';
ALTER TABLE continuity_notifications ALTER COLUMN result_code SET DEFAULT '';
ALTER TABLE continuity_notifications ADD COLUMN decision_id integer REFERENCES communication_decisions(id);
ALTER TABLE IF EXISTS attendance_followups ADD COLUMN IF NOT EXISTS owner_id integer REFERENCES users(id);
ALTER TABLE IF EXISTS attendance_followups ADD COLUMN IF NOT EXISTS cover_id integer REFERENCES users(id);
ALTER TABLE IF EXISTS attendance_followups ADD COLUMN IF NOT EXISTS due_at timestamp without time zone;
ALTER TABLE IF EXISTS attendance_followups ADD COLUMN IF NOT EXISTS escalated boolean NOT NULL DEFAULT false;


REVOKE ALL ON coordination_policies, communication_decisions, discharge_followups, care_referrals, referral_clinical_records, care_plan_reviews, care_review_signoffs, coordination_history FROM PUBLIC, anon, authenticated;

REVOKE ALL ON SEQUENCE coordination_policies_id_seq, communication_decisions_id_seq, discharge_followups_id_seq, care_referrals_id_seq, referral_clinical_records_id_seq, care_plan_reviews_id_seq, care_review_signoffs_id_seq, coordination_history_id_seq FROM PUBLIC, anon, authenticated;

CREATE TABLE coordination_coverage (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	valid_until TIMESTAMP WITHOUT TIME ZONE, 
	approved_by_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (kind IN ('discharge','referral','review')), 
	CHECK (status IN ('granted','withdrawn')), 
	CHECK (status <> 'granted' OR valid_until IS NOT NULL), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(approved_by_id) REFERENCES users (id)
);
CREATE INDEX coordination_coverage_lookup ON coordination_coverage (institution_id, patient_id, user_id, kind, id);
REVOKE ALL ON coordination_coverage FROM PUBLIC, anon, authenticated;
REVOKE ALL ON SEQUENCE coordination_coverage_id_seq FROM PUBLIC, anon, authenticated;

-- Outbox guard functions/triggers are appended below before the version is committed.
-- Included verbatim in migration 008. No external delivery or new outbox is introduced.
CREATE FUNCTION ramosolo.coordination_guard_outbox() RETURNS trigger
LANGUAGE plpgsql SET search_path = ramosolo, pg_catalog AS $$
DECLARE patient_identity integer; decision communication_decisions%ROWTYPE; local_clock time;
BEGIN
 SELECT patient_id INTO patient_identity FROM appointments
  WHERE id=NEW.appointment_id AND institution_id=NEW.institution_id;
 IF patient_identity IS NULL OR NEW.channel <> 'in_app' THEN RETURN NEW; END IF;
 SELECT * INTO decision FROM communication_decisions
  WHERE institution_id=NEW.institution_id AND patient_id=patient_identity
    AND purpose='reminders' AND channel='portal' AND scope IN ('practice','*')
  ORDER BY id DESC LIMIT 1;
 IF NOT FOUND THEN RETURN NEW; END IF; -- existing explicit legacy reminder consent remains authoritative
 IF decision.status <> 'granted' OR decision.verified_at IS NULL OR decision.destination='' THEN
  IF NEW.state='sent' THEN RAISE EXCEPTION 'Optional reminder consent or destination no longer permits delivery' USING ERRCODE='23514'; END IF;
  IF NEW.state IN ('pending','failed') THEN
   NEW.state='cancelled'; NEW.sent_at=NULL; NEW.invalidated_at=timezone('UTC',now());
   NEW.result_code='coordination_consent_or_destination_changed';
  END IF;
 ELSIF NEW.state='sent' AND decision.contact_start IS NOT NULL AND decision.contact_end IS NOT NULL THEN
  local_clock=(now() AT TIME ZONE decision.timezone)::time;
  IF (decision.contact_start<=decision.contact_end AND NOT (local_clock BETWEEN decision.contact_start AND decision.contact_end))
    OR (decision.contact_start>decision.contact_end AND NOT (local_clock>=decision.contact_start OR local_clock<=decision.contact_end)) THEN
   RAISE EXCEPTION 'Optional reminder outside agreed contact window' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION ramosolo.coordination_suppress_withdrawn() RETURNS trigger
LANGUAGE plpgsql SET search_path = ramosolo, pg_catalog AS $$
BEGIN
 IF NEW.purpose='reminders' AND NEW.channel='portal' AND NEW.scope IN ('practice','*')
   AND (NEW.status <> 'granted' OR NEW.verified_at IS NULL OR NEW.destination='') THEN
  IF to_regclass('ramosolo.communication_preferences') IS NOT NULL THEN
   UPDATE communication_preferences SET in_app_enabled=false,version=version+1,
     changed_at=timezone('UTC',now()),changed_by=NEW.recorded_by_id
    WHERE institution_id=NEW.institution_id AND patient_id=NEW.patient_id AND in_app_enabled;
  END IF;
  IF to_regclass('ramosolo.notification_outbox') IS NOT NULL THEN
   WITH affected AS (
    UPDATE notification_outbox o SET state='cancelled',invalidated_at=timezone('UTC',now()),
      result_code='coordination_consent_or_destination_changed'
    WHERE o.institution_id=NEW.institution_id AND o.state IN ('pending','failed') AND o.sent_at IS NULL
      AND o.appointment_id IN (SELECT id FROM appointments WHERE patient_id=NEW.patient_id AND institution_id=NEW.institution_id)
    RETURNING o.id
   ) INSERT INTO audit_events(institution_id,actor_id,action,resource_type,resource_id,created_at)
     SELECT NEW.institution_id,NEW.recorded_by_id,'suppress_optional_notice','notification_outbox',id,timezone('UTC',now()) FROM affected;
  END IF;
 END IF;
 RETURN NEW;
END $$;

DO $$ BEGIN
 IF to_regclass('ramosolo.notification_outbox') IS NOT NULL THEN
  CREATE TRIGGER coordination_outbox_permission_guard BEFORE INSERT OR UPDATE ON ramosolo.notification_outbox
    FOR EACH ROW EXECUTE FUNCTION ramosolo.coordination_guard_outbox();
 END IF;
END $$;
CREATE TRIGGER coordination_consent_withdrawal AFTER INSERT ON ramosolo.communication_decisions
 FOR EACH ROW EXECUTE FUNCTION ramosolo.coordination_suppress_withdrawn();
REVOKE ALL ON FUNCTION ramosolo.coordination_guard_outbox(), ramosolo.coordination_suppress_withdrawn() FROM PUBLIC, anon, authenticated;

INSERT INTO schema_versions(version) VALUES (8);
COMMIT;
