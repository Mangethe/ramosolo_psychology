-- Review only. Rehearse after 017 on an isolated live-shaped database.
-- This history does not grant access or change patient-account links.
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE TABLE ramosolo.representative_authority_decisions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    institution_id integer NOT NULL,
    patient_id integer NOT NULL,
    representative_account_id integer NOT NULL,
    recorded_by_account_id integer NOT NULL,
    purpose text NOT NULL CHECK (purpose IN (
        'appointment_logistics', 'child_information_processing', 'treatment_consent')),
    outcome text NOT NULL CHECK (outcome IN ('granted', 'declined', 'withdrawn')),
    policy_version text NOT NULL CHECK (length(btrim(policy_version)) BETWEEN 1 AND 120),
    evidence_reference uuid NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    valid_until timestamptz,
    CHECK (representative_account_id <> recorded_by_account_id),
    CHECK ((outcome = 'granted' AND valid_until IS NOT NULL AND valid_until > recorded_at)
        OR (outcome <> 'granted' AND valid_until IS NULL)),
    FOREIGN KEY (patient_id, institution_id) REFERENCES ramosolo.patients (id, institution_id),
    FOREIGN KEY (representative_account_id, institution_id)
        REFERENCES ramosolo.memberships (user_id, institution_id),
    FOREIGN KEY (recorded_by_account_id, institution_id)
        REFERENCES ramosolo.memberships (user_id, institution_id)
);

CREATE INDEX representative_authority_decisions_latest
    ON ramosolo.representative_authority_decisions
    (institution_id, patient_id, representative_account_id, purpose, id DESC);

COMMENT ON TABLE ramosolo.representative_authority_decisions IS
    'Inactive, purpose-specific decisions. Append withdrawal evidence. Evaluate the latest decision before expiry.';
COMMENT ON COLUMN ramosolo.representative_authority_decisions.evidence_reference IS
    'Opaque reference to separately protected evidence. Store no document, ID number or date of birth here.';

ALTER TABLE ramosolo.representative_authority_decisions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ramosolo.representative_authority_decisions FROM PUBLIC;
REVOKE ALL ON SEQUENCE ramosolo.representative_authority_decisions_id_seq FROM PUBLIC;

DO $roles$
DECLARE
    member_role name;
BEGIN
    FOR member_role IN
        SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated',
            'service_role', 'authenticator', 'ramosolo_app_runtime', 'ramosolo_mail_worker')
    LOOP
        EXECUTE format('REVOKE ALL ON ramosolo.representative_authority_decisions FROM %I', member_role);
        EXECUTE format('REVOKE ALL ON SEQUENCE ramosolo.representative_authority_decisions_id_seq FROM %I', member_role);
    END LOOP;
END;
$roles$;

COMMIT;
