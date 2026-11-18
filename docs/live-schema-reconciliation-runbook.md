# Local migration 010 deployment checks and recovery runbook

## Scope and current state

This runbook covers only the local draft migrations/010_ramosolo_live_reconciliation_draft.sql. It was not applied to production. No production DDL, data, grants, migration history, seed records, or accounts were changed. Production checks below read catalog metadata only.

Current verdict: **ready for final review; NO-GO for production execution until a recoverable backup/PITR point and restore path are verified and separate execution approval is given**. The PostgreSQL 17 ordering defect is fixed; the latest read-only production catalog preflight and object-by-object comparison match the reviewed production snapshot. All requested isolated PostgreSQL 17.11 tests and the full suite passed with exit code 0. No production changes were made. Review the migration together with the booking mapping in scheduling_services.py and Med/MedWebsite/controllers/portal.py.

Final draft SHA-256:

~~~text
50067E6FE6898C494D153943242E4F277D9A50BC49695D01B51D69860E054A34  migrations/010_ramosolo_live_reconciliation_draft.sql
~~~

## Latest read-only production preflight

Refreshed on 2026-11-17 at 21:38 UTC through the named Supabase MCP against project `ramosolo` (`mavpwgqjgjnvopnnqnmb`). `get_project` returned `ACTIVE_HEALTHY`, database version `17.11.0.019` (PostgreSQL 17.11). The catalog query used schema-qualified object names and read only `pg_catalog`, `information_schema`, and `ramosolo.schema_versions`.

The SQL artifact still matches the approved SHA-256 above. The refreshed preflight matched the draft guards:

- Internal ledger remains versions 1–6; `ramosolo` is owned by `postgres`, with ACL `{postgres=UC/postgres}`.
- Inventory remains 30 tables, 29 sequences, 18 routines, 283 columns, 165 constraints, 72 indexes, and 32 non-internal triggers.
- Column, constraint, and index guard fingerprints remain `ba6cbdc54b6f7d5556337e7e84ce57f4`, `6e42b7f83cb9357f5abc713146cc4d22`, and `45d1bacda400cf0739382ce86a725090` respectively. The constraint fingerprint is generated with stable ordering and length-prefixed serialization.
- All 21 target tables, all four attendance-followup fields, and `admission_patient_identity` remain absent, as required by the migration preconditions.
- An object-level comparison found zero differences across all 165 constraints, 32 trigger definitions/enabled states, and 18 routine definitions/owners/ACLs/configuration/security flags. No existing table or sequence has an owner other than `postgres`; no applicable global or `ramosolo` default privileges were found.
- The catalog MCP connection reported `current_user=session_user=postgres` and `search_path="$user", public, extensions`; every inspected object was explicitly schema-qualified. The separately checked application connection previously reported `search_path=ramosolo, public`.

The target inventory and fingerprints still match the draft guards. The queries did not read application or patient rows and did not change production.

Production facts came from read-only catalog queries through the named Supabase MCP and the application's protected database connection. Production reported PostgreSQL 17.11 and internal schema ledger 1–6. The Supabase CLI timestamp ledger is separate; its remote rows do not match local files. Do not use Supabase CLI migration push/list/up to apply this draft.

## Reproduce the local artifact

Run these from the repository root in PowerShell. The fixture generator consumes only the metadata snapshot and emits synthetic sentinel rows.

~~~powershell
& '.venv/Scripts/python.exe' verification/build_live_schema_fixture.py
& '.venv/Scripts/python.exe' verification/build_reconciliation_draft.py
Get-FileHash -LiteralPath migrations/010_ramosolo_live_reconciliation_draft.sql -Algorithm SHA256
~~~

Expected generation output:

- tests/fixtures/ramosolo_live_fixture.sql written;
- migrations/010_ramosolo_live_reconciliation_draft.sql written;
- the PG17.11 fixture profile is read from tests/fixtures/ramosolo_pg17_fixture_profile.json;
- final SHA-256 equals the hash above.

The migration builder reads historical migrations 007–009 and the reviewed metadata snapshot. It does not write historical migrations.

## Test commands and results

Tests create a temporary loopback-only PostgreSQL cluster under C:\Temp with synthetic databases. They disable dotenv, use `DATABASE_URL=sqlite://` for the Flask default, and never accept or read a live database URL. PostgreSQL 17.11 binaries came from EDB's `postgresql-17.11-4-windows-x64-binaries.zip`; its verified SHA-256 was `b9424ee7bc60b52450ff910a3630225df32e633f3cb29c1d126d9299d59aea28`. The isolated server reported `17.11` (`server_version_num=170011`), matching production's patch version. The local EDB Windows build differs from Supabase's managed server platform/build.

Exact command against the actual checked-in migration file:

~~~powershell
$env:PYTHON_DOTENV_DISABLED='1'; $env:APP_ENV='test'; $env:DATABASE_URL='sqlite://'; $env:SUPABASE_DB_URL=''; $env:FLASK_SECRET_KEY='synthetic-reconciliation-validation'; $env:RAMOSOLO_POSTGRES_BIN='C:\Temp\postgresql-17.11-binaries\pgsql\bin'; $env:RAMOSOLO_POSTGRES_MAJOR='17'; & '.venv/Scripts/python.exe' -m pytest -v -s tests/test_independent_postgres.py::test_factory_cli_schema_after_rollback_and_connection_reuse tests/test_independent_postgres.py::test_reconciliation_draft_aborts_atomically_on_incompatible_catalog tests/test_independent_postgres.py::test_reconciliation_draft_applies_to_reconstructed_production_fixture tests/test_independent_postgres.py::test_reconciliation_draft_rejects_observed_schema_drift_atomically tests/test_independent_postgres.py::test_reconciliation_draft_rolls_back_after_midflight_failure tests/test_independent_postgres.py::test_reconciliation_draft_rolls_back_when_postcondition_fails tests/test_independent_postgres.py::test_reconciliation_migrated_fixture_supports_app_writes_and_boundaries --tb=short
~~~

Result on PostgreSQL 17.11: **7 passed**. Startup/CLI schema-after-rollback and connection reuse, incompatible-catalog abort, successful apply, observed schema-drift rejection, mid-flight rollback, failed-postcondition rollback, and migrated-app writes/boundaries all passed using the actual checked-in SQL file. The additional `test_constraint_fingerprint_is_order_stable_and_rejects_definition_drift` also passed: reversed catalog input produced the same fingerprint, while a changed appointment status constraint was rejected atomically.

The full suite completed on the same isolated PostgreSQL 17.11 configuration with **254 passed, 1 skipped, 3 xfailed, 6 warnings; exit code 0** in 478.89 seconds. The skip is the retained, conditionally skipped stale demo-seed prototype described below. No tests were excluded with `--ignore`.

Fingerprint regression command:

~~~powershell
$env:PYTHON_DOTENV_DISABLED='1'; $env:APP_ENV='test'; $env:DATABASE_URL='sqlite://'; $env:SUPABASE_DB_URL=''; $env:FLASK_SECRET_KEY='synthetic-reconciliation-validation'; $env:RAMOSOLO_POSTGRES_BIN='C:\Temp\postgresql-17.11-binaries\pgsql\bin'; $env:RAMOSOLO_POSTGRES_MAJOR='17'; & '.venv/Scripts/python.exe' -m pytest -v -s tests/test_independent_postgres.py::test_constraint_fingerprint_is_order_stable_and_rejects_definition_drift --tb=short
~~~

Full-suite command:

~~~powershell
$env:PYTHON_DOTENV_DISABLED='1'; $env:APP_ENV='test'; $env:DATABASE_URL='sqlite://'; $env:SUPABASE_DB_URL=''; $env:FLASK_SECRET_KEY='synthetic-reconciliation-full-suite'; $env:RAMOSOLO_POSTGRES_BIN='C:\Temp\postgresql-17.11-binaries\pgsql\bin'; $env:RAMOSOLO_POSTGRES_MAJOR='17'; & '.venv/Scripts/python.exe' -m pytest -q
~~~

`tests/test_demo_seed.py` and sibling `demo_seed.py` are untracked in this checkout. The prototype refers to 11 ORM classes absent from `models` and imports the absent `Med/MedWebsite/reminders.py`; making it work would add a separate legacy demo subsystem. The test source is retained and performs an explicit module-level `pytest.skip` only while those dependencies are absent. The full suite included the module; its documented skip accounts for the single skip in the full-suite result. No test path was excluded.

## Read-only preflight before any future review-approved application

Use the actual app database connection to identify the role. Do not read .env or print the connection URL. This query reads only session/catalog metadata:

~~~sql
SELECT current_user, session_user, current_setting('search_path') AS search_path,
       current_setting('server_version_num')::integer AS server_version_num,
       has_schema_privilege(current_user, 'ramosolo', 'USAGE') AS schema_usage;

SELECT c.relname, pg_get_userbyid(c.relowner) AS owner,
       has_table_privilege(current_user, c.oid, 'SELECT') AS can_select,
       has_table_privilege(current_user, c.oid, 'INSERT') AS can_insert,
       has_table_privilege(current_user, c.oid, 'UPDATE') AS can_update,
       has_table_privilege(current_user, c.oid, 'DELETE') AS can_delete
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'ramosolo' AND c.relkind IN ('r', 'p')
ORDER BY c.relname;

SELECT c.relname, pg_get_userbyid(c.relowner) AS owner,
       has_sequence_privilege(current_user, c.oid, 'USAGE') AS can_use,
       has_sequence_privilege(current_user, c.oid, 'SELECT') AS can_read,
       has_sequence_privilege(current_user, c.oid, 'UPDATE') AS can_update
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'ramosolo' AND c.relkind = 'S'
ORDER BY c.relname;
~~~

Before considering the SQL, also verify these catalog-only checks from the same role that will execute it:

~~~sql
SELECT version FROM ramosolo.schema_versions ORDER BY version;

SELECT current_setting('server_version_num')::integer AS server_version_num,
       pg_get_userbyid(n.nspowner) AS schema_owner,
       n.nspacl::text AS schema_acl
FROM pg_namespace n
WHERE n.nspname = 'ramosolo';

SELECT pg_get_userbyid(d.defaclrole) AS owner,
       CASE WHEN d.defaclnamespace = 0 THEN '<global>' ELSE n.nspname END AS schema_name,
       d.defaclobjtype, d.defaclacl
FROM pg_default_acl d
LEFT JOIN pg_namespace n ON n.oid = d.defaclnamespace
WHERE d.defaclrole = 'postgres'::regrole
  AND (d.defaclnamespace = 0 OR n.nspname = 'ramosolo');

SELECT to_regclass('ramosolo.appointment_proposals') AS appointment_proposals,
       to_regclass('ramosolo.calendar_delegations') AS calendar_delegations,
       to_regclass('ramosolo.calendar_history') AS calendar_history;
~~~

Fresh read-only preflight returned versions 1–6; 30 tables, 29 sequences, 18 routines, 283 columns, 165 non-not-null constraints, 72 indexes, and 32 enabled triggers; all 21 migration target tables absent; the four attendance-followup fields absent; and `admission_patient_identity` absent. Column fingerprint `ba6cbdc54b6f7d5556337e7e84ce57f4` and index fingerprint `45d1bacda400cf0739382ce86a725090` match the draft. A refreshed object-by-object comparison found zero missing/extra or definition/type/flag differences among the 165 production constraints; all 18 routines and all 32 trigger definitions/enabled states also match.

The canonical production constraint fingerprint is `6e42b7f83cb9357f5abc713146cc4d22`; a fresh SQL query using the generated guard expression returned the same value on production (server_version_num `170011`, 165 constraints). The fixture fingerprint is `0ecc63c7f166d59e8d2a4c94de7aa685`. The fixture builder replays the reviewed definition text as DDL; EDB PostgreSQL 17.11 re-renders 18 equivalent CHECK expressions with different array-cast placement or associative-AND parentheses. Object names, types, and deferrability/deferred/validated flags match for all 165; the differences are limited to those 18 rendered definition strings. The migration accepts only the exact production fingerprint or this separately recorded, complete synthetic fixture fingerprint. The regression verifies that an altered constraint matches neither.

The app's protected connection reports `current_user=postgres`, `session_user=postgres`, search path `ramosolo, public`, server 17.11, schema USAGE/CREATE true, `rolsuper=false`, and `rolbypassrls=true`. Effective privileges are SELECT/INSERT/UPDATE/DELETE on all 30 current tables, USAGE/SELECT/UPDATE on all 29 sequences, and EXECUTE on all 18 routines. The draft creates new tables, sequences, and functions as `postgres` and adds no application grants; no permission change is required for the current runtime role. It does not grant `anon` or `authenticated`. Since the runtime role has BYPASSRLS, application institution/role scoping remains necessary; the migrated-fixture boundary tests exercise those application paths. Do not change grants as part of this reconciliation.

## Expected changes after a separately approved application

- Add the 21 missing application tables from migrations 007–009.
- Add four absent fields on existing attendance_followups: owner_id, cover_id, due_at, escalated.
- Add unique index admissions(id, patient_id) if absent.
- Add two coordination/consent triggers and functions on notification_outbox and communication_decisions.
- Enable RLS on calendar_delegations, appointment_proposals, and calendar_history as defined in 009.
- Record internal schema versions 7, 8, and 9 only after every postcondition succeeds.
- Preserve existing appointments, financial rows, reminder/consent rows, scheduling/assignment/audit triggers, grants, and Supabase CLI migration history.

## Locking and transaction behavior

The SQL uses one transaction, an advisory transaction lock named ramosolo_live_reconciliation, a 5-second lock timeout, and a 5-minute statement timeout. The advisory lock serializes this draft with copies using the same lock name; it does not pause normal application writes or coordinate with scripts using the older ramosolo_coordination_migrations lock.

Table creation is additive. Adding the four attendance_followups fields and foreign keys can take locks on that table and referenced tables; the lock timeout should abort rather than wait for more than five seconds. PostgreSQL 17 uses a fast metadata default for the non-null boolean default, but ALTER TABLE still needs a brief strong lock. Schedule any future approved run in a quiet window, check active transactions, and do not run other schema migrations concurrently.

The SQL changes no existing appointment/reminder row values. It installs functions/triggers that affect future consent/outbox writes. Transaction failure before COMMIT rolls back created tables, fields, indexes, triggers/functions, and ledger inserts together.

## Backup and recovery prerequisites

**No production backup or PITR point has been verified, and recoverability is not claimed.** The latest read-only `get_project` response reported `ACTIVE_HEALTHY` and database version `17.11.0.019`, but returned no backup fields. The connected Supabase MCP has no backup-list operation. Its project restore tool is mutating and was not called.

The repository's bundled Supabase CLI was tried from `C:\Temp` with telemetry disabled so it would not inspect the checkout's `.env` or write telemetry. `backups list --remote=mavpwgqjgjnvopnnqnmb` returned `AccessTokenRequiredError: Access token not provided`; it returned no backup metadata. The global `supabase` command is not installed on PATH. No restore was started.

An authorized project operator must provide one of these read-only metadata paths:

1. From an authenticated Supabase CLI session, run:

~~~powershell
$env:SUPABASE_TELEMETRY_DISABLED='1'
supabase backups list --remote=mavpwgqjgjnvopnnqnmb
~~~

   The CLI must be authenticated privately to the correct project. Do not paste or send the token. The bundled executable in this checkout can also be called from `C:\Temp` by its full path; it currently has no access token in this environment.

2. From a shell holding a scoped Management API token in `SUPABASE_ACCESS_TOKEN`, run this read-only PowerShell request:

~~~powershell
$backupHeaders = @{ Authorization = "Bearer $env:SUPABASE_ACCESS_TOKEN" }
Invoke-RestMethod -Method Get `
  -Uri 'https://api.supabase.com/v1/projects/mavpwgqjgjnvopnnqnmb/database/backups' `
  -Headers $backupHeaders | ConvertTo-Json -Depth 8
~~~

   The endpoint requires OAuth scope `database:read` and fine-grained permission `backups_read`. Keep the token private; share only the returned backup/PITR metadata. Supabase also exposes the same listing in **Project ramosolo > Database > Backups**. ([Management API](https://supabase.com/docs/reference/api/v1-list-all-backups), [CLI command](https://supabase.com/docs/reference/cli/supabase-backups-list))

Before production approval, record either a `COMPLETED` physical backup's UTC `inserted_at` and `is_physical_backup` status, or the PITR enabled state and earliest/latest recovery times. The selected point must be before the migration and recent enough for the required recovery objective. If no suitable point exists, the project operator must enable/arrange physical backups or PITR and wait for a usable recovery point. Do not treat a listed backup alone as a verified restore.

### Restore verification procedure

After a suitable point is confirmed, the project operator must verify recovery to a separate, access-controlled project before production execution:

1. In the source project, open **Database > Backups > Restore to a New Project**.
2. Select the completed physical backup or the PITR timestamp immediately before the planned migration.
3. Review the new project's cost and region, create the isolated restore project, and restrict access because the copy contains live database records and auth data.
4. When the restore finishes, use catalog-only checks to verify the database is reachable, the PostgreSQL version is compatible, and the restored `ramosolo` schema has ledger versions 1–6 and the pre-migration inventory. Do not inspect patient rows or run the migration against the restore copy as a substitute for the already completed fixture tests.
5. Record the restore project's identifier, selected backup/PITR UTC point, completion time, and verification result. Do not send credentials or patient data.

Supabase's restore-to-new-project workflow requires physical backups and a paid plan, may incur new-project costs, and copies database data and roles. PITR time ranges and restoration behavior are described in the official [backup guide](https://supabase.com/docs/guides/platform/backups) and [restore-to-new-project guide](https://supabase.com/docs/guides/platform/clone-project). This review did not initiate that workflow.

If a future approved application fails before COMMIT, let PostgreSQL roll back the transaction and verify ledger 1–6 plus the absent target objects. If the connection drops around COMMIT, inspect the ledger and complete postconditions before retrying. If a corrected migration commits but later requires recovery, use the verified restore plan; do not manually drop tables, edit the ledger, or replay historical migrations.

## Future execution plan (not performed)

**Target:** production Supabase project `ramosolo` (`mavpwgqjgjnvopnnqnmb`), schema `ramosolo`, executed as the authorized `postgres` role.

**Tool:** Supabase Dashboard **SQL Editor** for that exact project. The migration is a local draft with its own `BEGIN`/`COMMIT` and internal `schema_versions` ledger; do not use `supabase db push`, `supabase migration up`, or MCP `apply_migration` (the Supabase CLI timestamp ledger is separate).

After the backup/PITR and isolated restore prerequisites are satisfied and separate production execution approval is given:

1. Re-run `Get-FileHash -LiteralPath 'migrations/010_ramosolo_live_reconciliation_draft.sql' -Algorithm SHA256` and require `50067E6FE6898C494D153943242E4F277D9A50BC49695D01B51D69860E054A34`.
2. Copy the exact reviewed SQL locally with `Get-Content -Raw -LiteralPath 'migrations/010_ramosolo_live_reconciliation_draft.sql' | Set-Clipboard`.
3. In the project's SQL Editor, create one query, paste the complete file, visually confirm the project reference and schema, and run once as `postgres`. Do not split the script or remove its transaction statements.
4. Confirm the editor reports successful COMMIT. If it reports any error, do not rerun immediately; use the recovery steps below.
5. Run catalog-only postchecks. Confirm versions 1–9, all 21 target tables, four attendance fields, `admission_patient_identity`, 34 enabled triggers, the two new routine/trigger bindings, owner/ACL state, and the unchanged existing routine/trigger definitions.
6. From the actual app connection, confirm the active institution schema and required privileges. Then perform read-only app smoke checks for login, dashboard, appointments, and calendar. Do not create a real patient appointment as a smoke test.

## Recovery and rerun

If the SQL reports an error before COMMIT:

1. Let the SQL session end or explicitly roll back its failed transaction.
2. Run read-only checks for versions, the 21 target tables, the four attendance fields, and admission_patient_identity.
3. Expected atomic-failure state is versions 1–6, no target tables/fields/index, and unchanged existing objects. If any result differs, stop and capture catalog metadata for review.
4. Do not manually drop an object, edit the ledger, or run historical migrations to repair it. Correct the draft only after identifying the exact state difference, then repeat isolated tests.

If the connection is lost during final COMMIT, inspect the ledger and full postconditions before doing anything. If versions are 1–9 and every postcondition is exact, treat it as applied and do not rerun. If versions are 1–6 and no target changes remain, the transaction rolled back. Any mixed state requires catalog reconciliation and review; do not mark versions complete manually.

The tested second-application behavior is an intentional exception: after a successful apply, it aborts at the ledger precondition and leaves versions 1–9, objects, and synthetic appointment unchanged.
