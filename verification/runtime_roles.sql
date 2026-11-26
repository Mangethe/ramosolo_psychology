-- Review candidate. Execute only in an isolated synthetic database unless separately approved.
-- Run as the migration owner after 010–017. Roles have no login or inherited membership.
BEGIN;
CREATE ROLE ramosolo_app_runtime NOLOGIN NOINHERIT NOCREATEROLE NOCREATEDB NOBYPASSRLS;
CREATE ROLE ramosolo_mail_worker NOLOGIN NOINHERIT NOCREATEROLE NOCREATEDB NOBYPASSRLS;
GRANT USAGE ON SCHEMA ramosolo TO ramosolo_app_runtime, ramosolo_mail_worker;

GRANT SELECT ON ramosolo.institutions, ramosolo.public_holidays, ramosolo.schema_versions
    TO ramosolo_app_runtime;
GRANT SELECT, INSERT, UPDATE ON
    ramosolo.users, ramosolo.memberships, ramosolo.patients, ramosolo.care_assignments,
    ramosolo.appointments, ramosolo.admissions, ramosolo.booking_requests,
    ramosolo.availability_policies, ramosolo.availability_sessions, ramosolo.availability_exceptions,
    ramosolo.calendar_blocks, ramosolo.calendar_delegations, ramosolo.appointment_proposals,
    ramosolo.patient_permissions, ramosolo.external_practitioners, ramosolo.patient_preferences,
    ramosolo.care_plans, ramosolo.continuity_events, ramosolo.continuity_notifications,
    ramosolo.coordination_coverage, ramosolo.coordination_policies, ramosolo.discharge_followups,
    ramosolo.care_referrals, ramosolo.care_plan_reviews,
    ramosolo.portal_sessions, ramosolo.account_verifications, ramosolo.account_recoveries,
    ramosolo.authenticators, ramosolo.auth_recovery_codes, ramosolo.pending_authentications,
    ramosolo.federated_identities, ramosolo.oidc_exchanges, ramosolo.phone_challenges,
    ramosolo.verified_phones, ramosolo.security_emails, ramosolo.delivery_limits
    TO ramosolo_app_runtime;
GRANT SELECT, INSERT ON
    ramosolo.audit_events, ramosolo.calendar_history, ramosolo.clinical_records,
    ramosolo.nursing_observations, ramosolo.communication_decisions, ramosolo.continuity_history,
    ramosolo.referral_clinical_records, ramosolo.care_review_signoffs, ramosolo.coordination_history,
    ramosolo.appointment_emails TO ramosolo_app_runtime;
GRANT DELETE ON ramosolo.care_assignments, ramosolo.authenticators TO ramosolo_app_runtime;

-- Existing invoker triggers and explicit portal compatibility reads on the live-shaped baseline.
GRANT SELECT ON ramosolo.communication_preferences, ramosolo.reminder_leads,
    ramosolo.reminder_policies, ramosolo.followup_policies TO ramosolo_app_runtime;
GRANT SELECT, INSERT, UPDATE ON ramosolo.booking_rate_limits, ramosolo.attendance_followups,
    ramosolo.notification_outbox TO ramosolo_app_runtime;
GRANT SELECT, INSERT ON ramosolo.appointment_attendance_events,
    ramosolo.notification_attempts TO ramosolo_app_runtime;
GRANT EXECUTE ON FUNCTION ramosolo.followup_actor_allowed(integer, integer, integer, boolean),
    ramosolo.invalidate_reminder_jobs(integer, integer, integer, text),
    ramosolo.reminder_job_current(ramosolo.notification_outbox) TO ramosolo_app_runtime;

-- The worker can claim jobs and read delivery eligibility only. A row lock requires UPDATE on
-- at least one column. The policies below permit that lock and reject any row update.
GRANT SELECT (id, email, enabled) ON ramosolo.users TO ramosolo_mail_worker;
GRANT SELECT (user_id, verified_at, verified_email, verification_id, requested_email, expires_at)
    ON ramosolo.account_verifications TO ramosolo_mail_worker;
GRANT SELECT (id, institution_id, user_id, email), UPDATE (id)
    ON ramosolo.patients TO ramosolo_mail_worker;
GRANT SELECT (id, patient_id, institution_id, status, schedule_version, starts_at), UPDATE (id)
    ON ramosolo.appointments TO ramosolo_mail_worker;
GRANT SELECT (id, kind) ON ramosolo.institutions TO ramosolo_mail_worker;
GRANT SELECT (id, institution_id, user_id, role, enabled) ON ramosolo.memberships TO ramosolo_mail_worker;
GRANT SELECT ON ramosolo.appointment_emails, ramosolo.communication_decisions,
    ramosolo.patient_preferences TO ramosolo_mail_worker;
GRANT SELECT, UPDATE (state, attempts, next_attempt_at, last_run_id, result_code)
    ON ramosolo.security_emails TO ramosolo_mail_worker;
GRANT SELECT, INSERT, UPDATE ON ramosolo.email_delivery_runs, ramosolo.delivery_limits TO ramosolo_mail_worker;

ALTER TABLE ramosolo.patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE ramosolo.appointments ENABLE ROW LEVEL SECURITY;
CREATE POLICY mail_lock_patient ON ramosolo.patients FOR UPDATE TO ramosolo_mail_worker
    USING (true) WITH CHECK (false);
CREATE POLICY mail_lock_appointment ON ramosolo.appointments FOR UPDATE TO ramosolo_mail_worker
    USING (true) WITH CHECK (false);

DO $roles$
DECLARE
    item record;
BEGIN
    FOR item IN SELECT c.oid::regclass AS relation,
            has_table_privilege('ramosolo_app_runtime', c.oid, 'SELECT') AS portal,
            has_any_column_privilege('ramosolo_mail_worker', c.oid, 'SELECT') AS worker
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'ramosolo' AND c.relkind = 'r' AND c.relrowsecurity
    LOOP
        IF item.portal THEN
            EXECUTE format('CREATE POLICY portal_service ON %s TO ramosolo_app_runtime USING (true) WITH CHECK (true)',
                item.relation);
        END IF;
        IF item.worker THEN
            IF item.relation IN ('ramosolo.security_emails'::regclass, 'ramosolo.email_delivery_runs'::regclass,
                                'ramosolo.delivery_limits'::regclass) THEN
                EXECUTE format('CREATE POLICY mail_queue ON %s TO ramosolo_mail_worker USING (true) WITH CHECK (true)',
                    item.relation);
            ELSE
                EXECUTE format('CREATE POLICY mail_lookup ON %s FOR SELECT TO ramosolo_mail_worker USING (true)',
                    item.relation);
            END IF;
        END IF;
    END LOOP;
    -- Only owned serial/identity sequences for relations this role can insert into.
    FOR item IN SELECT DISTINCT s.oid::regclass AS sequence
        FROM pg_class s JOIN pg_depend d ON d.objid = s.oid AND d.classid = 'pg_class'::regclass
        JOIN pg_class t ON t.oid = d.refobjid AND d.refclassid = 'pg_class'::regclass
        JOIN pg_namespace n ON n.oid = s.relnamespace
        WHERE n.nspname = 'ramosolo' AND s.relkind = 'S' AND d.deptype IN ('a','i')
          AND has_table_privilege('ramosolo_app_runtime', t.oid, 'INSERT')
    LOOP
        EXECUTE format('GRANT USAGE ON SEQUENCE %s TO ramosolo_app_runtime', item.sequence);
    END LOOP;
END;
$roles$;

-- Restrict current functions; review each future invocation and set equivalent default
-- privileges for the actual migration owner before enabling a service login.
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA ramosolo FROM PUBLIC;
COMMIT;
