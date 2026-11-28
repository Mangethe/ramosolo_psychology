-- Permission draft. Apply in a synthetic replay after migrations 010–017 and
-- verification/runtime_roles.sql. The latter provisions the two NOLOGIN roles.
-- Run as the migration owner with authority over the named objects and roles.
BEGIN;

-- These roles are grant containers. Keep owner/admin access out of their role chains.
DO $service_roles$
BEGIN
    IF EXISTS (
        SELECT FROM pg_roles AS r
        WHERE r.rolname IN ('ramosolo_app_runtime', 'ramosolo_mail_worker')
          AND (r.rolcanlogin OR r.rolsuper OR r.rolcreaterole OR r.rolcreatedb
               OR r.rolreplication OR r.rolbypassrls
               OR EXISTS (SELECT FROM pg_auth_members AS m WHERE m.member = r.oid)
               OR EXISTS (SELECT FROM pg_namespace AS n
                          WHERE n.nspname = 'ramosolo' AND n.nspowner = r.oid)
               OR EXISTS (SELECT FROM pg_class AS c
                          WHERE c.relnamespace = 'ramosolo'::regnamespace AND c.relowner = r.oid)
               OR EXISTS (SELECT FROM pg_proc AS p
                          WHERE p.pronamespace = 'ramosolo'::regnamespace AND p.proowner = r.oid))
    ) THEN
        RAISE EXCEPTION 'A Ramosolo service role can log in, has elevated flags or membership, or owns private objects';
    END IF;
END;
$service_roles$;

GRANT DELETE ON ramosolo.portal_sessions, ramosolo.pending_authentications,
    ramosolo.auth_recovery_codes TO ramosolo_app_runtime;
GRANT DELETE ON ramosolo.oidc_exchanges TO ramosolo_app_runtime;
REVOKE UPDATE ON ramosolo.oidc_exchanges FROM ramosolo_app_runtime;

GRANT SELECT, INSERT ON ramosolo.attendance_followup_reviews TO ramosolo_app_runtime;
GRANT USAGE ON SEQUENCE ramosolo.attendance_followup_reviews_id_seq TO ramosolo_app_runtime;

-- Provisioning/recovery, cleanup, and provider delivery run separately from web requests.
REVOKE ALL ON ramosolo.account_recoveries FROM ramosolo_app_runtime;
REVOKE INSERT, UPDATE ON ramosolo.availability_policies, ramosolo.availability_sessions,
    ramosolo.availability_exceptions FROM ramosolo_app_runtime;
REVOKE UPDATE ON ramosolo.federated_identities FROM ramosolo_app_runtime;
REVOKE UPDATE ON ramosolo.security_emails FROM ramosolo_app_runtime;
GRANT UPDATE (state) ON ramosolo.security_emails TO ramosolo_app_runtime;

-- Verify that both public and inherited API grants leave the private schema closed.
-- Abort on hosted drift so the owner can review the actual grant and its origin.
DO $private$
BEGIN
    IF EXISTS (
        SELECT FROM pg_roles AS r
        WHERE r.rolname IN ('anon', 'authenticated', 'service_role', 'authenticator')
          AND (has_schema_privilege(r.oid, 'ramosolo', 'USAGE,CREATE')
               OR pg_has_role(r.oid, 'ramosolo_app_runtime', 'MEMBER')
               OR pg_has_role(r.oid, 'ramosolo_mail_worker', 'MEMBER')
               OR EXISTS (
                   SELECT FROM pg_class AS c
                   WHERE c.relnamespace = 'ramosolo'::regnamespace
                     AND CASE
                         WHEN c.relkind = 'S' THEN has_sequence_privilege(r.oid, c.oid, 'USAGE,SELECT,UPDATE')
                         WHEN c.relkind IN ('r', 'p', 'v', 'm', 'f') THEN
                             has_table_privilege(r.oid, c.oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                             OR has_any_column_privilege(r.oid, c.oid, 'SELECT,INSERT,UPDATE,REFERENCES')
                         ELSE false
                     END
               )
               OR EXISTS (
                   SELECT FROM pg_proc AS p
                   WHERE p.pronamespace = 'ramosolo'::regnamespace
                     AND has_function_privilege(r.oid, p.oid, 'EXECUTE')
               ))
    ) THEN
        RAISE EXCEPTION 'A Data API role has Ramosolo privileges or service-role membership';
    END IF;
END;
$private$;

COMMIT;
