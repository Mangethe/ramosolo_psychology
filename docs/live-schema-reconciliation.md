# Ramosolo live schema reconciliation

Assessment date: 17 November 2026. Production was inspected through the named Supabase MCP using catalog-only queries. No patient/appointment rows were queried; no production DDL, grants, seed records, or ledger entries were changed.

## Verdict

**Ready for review; no production application yet.** The PostgreSQL 17 ordering defect is fixed, the refreshed live fingerprint matches the snapshot, and the isolated PostgreSQL 17.11 tests pass. Production execution remains blocked until a current backup/PITR point and its restore path are verified and separately approved.

The generator, migration guard, and fixture now share an unambiguous UTF-8 byte-length-prefixed serialization and explicit byte-stable ordering. The production catalog’s canonical fingerprint matches the reviewed snapshot. The isolated PG17.11 fixture has its own exact fingerprint because its deparser re-renders 18 equivalent CHECK definitions with cast-placement or redundant-parenthesis differences after reconstructing the snapshot text; the full fixture profile is separately bound, and any other definition change aborts.

Migration SHA-256: **50067E6FE6898C494D153943242E4F277D9A50BC49695D01B51D69860E054A34** — migrations/010_ramosolo_live_reconciliation_draft.sql.

The migration and local booking-value compatibility change in scheduling_services.py and Med/MedWebsite/controllers/portal.py should be reviewed together. The protected application connection reports runtime role `postgres`: all current table/sequence/function operations are effective. That role has `BYPASSRLS`, so application institution and role scoping remains necessary. The isolated test server was PostgreSQL 17.11, matching production's patch version; its EDB Windows build differs from Supabase's managed platform.

## Production catalog evidence

The read-only snapshot is tests/fixtures/ramosolo_live_catalog.json; its generated, synthetic-only reconstruction is tests/fixtures/ramosolo_live_fixture.sql. The snapshot includes columns and defaults, constraints, indexes, sequences, functions and source hashes, triggers and definitions, table/function ACLs, ownership, RLS flags, and default-privilege results.

| Catalog item | Observed production state | Reconciliation evidence |
|---|---|---|
| PostgreSQL | 17.11 (server_version_num=170011) | Read-only Supabase catalog query. Draft accepts the observed major version and PostgreSQL 18 for the local fixture. |
| ramosolo.schema_versions | Exactly versions 1–6 | Fixture preserves 1–6. Draft inserts 7–9 only after its complete postcondition block. |
| Tables / columns | 30 tables / 283 columns | Fixture test compares every name, ordinal, type, default, identity/generated marker, and nullability against the snapshot. |
| Constraints | 165 non-not-null constraints | Fresh read-only comparison found no missing/extra constraints and zero differences in name, type, definition, deferrability, deferred state, or validation. Canonical production fingerprint: `6e42b7f83cb9357f5abc713146cc4d22`; a live SQL calculation matched it. The synthetic EDB PG17.11 reconstruction has a separately bound exact fingerprint, `0ecc63c7f166d59e8d2a4c94de7aa685`, because 18 definitions are re-rendered with equivalent cast placement or redundant parentheses. |
| Indexes | 72 | Every reconstructed pg_indexes.indexdef matches the snapshot. Draft fingerprints the complete index inventory and every definition, including booking_capacity. |
| Sequences | 29 | Fixture compares type, increment, min/max, start/cache/cycle, owner, and ACL for every sequence. |
| Functions | 18, all owned by postgres, not SECURITY DEFINER, configured with search_path=ramosolo, pg_temp | Fixture compares exact prosrc MD5, owner, configuration, security flag, and ACL. Draft checks inventory and each source hash before and after DDL. |
| Triggers | 32 user triggers, all tgenabled=O | Read-only Supabase query returned O for all 32. Fixture compares all definitions and enabled states. Draft checks each definition and enablement before/after; postcondition requires both new triggers enabled. |
| Ownership and ACLs | Schema, tables, sequences, and functions owned by postgres; observed table/sequence/function ACLs are owner-only; anon and authenticated have no object grants | Fixture compares all table/function/sequence ACLs and owners. Draft rejects ownership drift and non-owner grants; it creates no runtime grants. |
| Default privileges | No global or ramosolo default ACL rows for postgres | Fixture checks the same catalog query; draft aborts if matching default privileges are present. |
| RLS | Existing production tables have RLS disabled; no policies were observed | Fixture preserves each table’s RLS flags. Draft enables RLS on the three new calendar tables as in migration 009; no policy or grant is added. |
| Schema ACL | Namespace owner postgres, ACL {postgres=UC/postgres} | Fixture asserts exact owner and ACL. Draft rejects grants to any non-owner. |

Existing trigger-to-function/source-hash evidence is preserved in the snapshot and bound by the migration. Key functions:

| Function | MD5 of pg_proc.prosrc |
|---|---|
| appointment_attendance_event | 9e91e5561f2cdafaeafb8a91bcbcf484 |
| booking_appointment_guard | d9713aa1040af31189bb0e30e3115248 |
| booking_config_guard | cd1ddad5ffab5ee73012a534ca9eebed |
| booking_exception_audit | 1a809621f31768c27022f14f1be4da69 |
| calendar_appointment_metadata | 8c7fa0f0431fbbcf41223cae5ea61d6c |
| calendar_block_guard | d349b9ab86c3429f53e439aa409d035e |
| financial_audit | 6e2394f201f09e24e250fe95d501b985 |
| followup_actor_allowed | 01c75ddc7bc63863c8db293884a0d2d5 |
| followup_guard | d70963d85293a7ac5b6d2b39aedb87f9 |
| invalidate_reminder_jobs | 27fe0e41e15fd3acd344daf9052fd35c |
| medical_assignment_guard | df43c9d5a3008225990b7419aab40b86 |
| medical_invoice_guard | d33780a803d1a24a7d737c8d9882daf0 |
| medical_payment_guard | 2db24f785ca8a3140991480d323a991e |
| notification_outbox_guard | 9e685225c72ec43064d55d53011329bd |
| reminder_configuration_guard | df4237a5ada4b48a7b9ec5f9a8ddc1ab |
| reminder_delivery_guard | 4ca822b50eaf738e56516208c7518203 |
| reminder_job_current | f457d575e0b28d04dda55a446487660f |
| reminder_source_invalidation | c3aeea35cb0d1d9e61af94c70edbf111 |

The 32 trigger definitions compared by the fixture are listed by table/name in the snapshot. The appointment set is appointment_assignment_scope, appointment_attendance_history, appointment_capacity_guard, appointment_metadata_guard, and appointment_reminder_invalidation. Assignment, attendance/audit, availability, calendar block, follow-up, invoice/payment, consent, and reminder delivery/outbox triggers also match exactly.

## Object-by-object reconciliation

### Existing objects

| Object | State | Outcome and evidence |
|---|---|---|
| appointments | Present with required institution_id integer NOT NULL, schedule_version integer NOT NULL DEFAULT 1, interval/calendar fields, production-only fields, constraints and indexes | Preserved byte-for-byte for the synthetic sentinel row. Draft checks full column fingerprint, inventory, critical identity/interval constraints, exact booking_capacity, and all appointment trigger/function definitions. Flask writes explicitly supply institution and complete interval values. |
| Appointment identity/interval guards | appointment_identity enforces patient-vs-booking-request identity; appointment_interval enforces end/occupancy order | Exact definitions compared in fixture and guarded by draft. Direct trigger writes are tested after migration. |
| Scheduling policies/sessions/exceptions, public holidays, calendar_blocks | Present with production indexes, checks, and guard/audit triggers | Preserved; all source and trigger hashes are checked. Synthetic valid session setup passes the live overlap guard. |
| attendance_followups / attendance_followup_reviews | Present; the 008 ownership/deadline fields are absent | Draft requires all four fields absent, then adds owner_id, cover_id, due_at, and escalated. Existing rows are not updated; PostgreSQL supplies the boolean default. Existing guard and review triggers remain unchanged. |
| Admissions | Present; composite (id, patient_id) identity index is absent | 008 adds admission_patient_identity; draft permits only absent or exact-definition state, then verifies the exact unique index. |
| Reminder and communication tables | Present, including communication_preferences, reminder_policies, reminder_leads, notification_outbox, notification_attempts, and in_app_notifications | Existing definitions, guards, and reminder invalidation remain unchanged. The new 008 hooks are added only after absence checks, with exact routine/trigger postconditions. |
| Core institutions, users, memberships, patients, admissions, audit, invoice/payment, booking, and availability objects | Present with production-only fields/constraints where observed | Fixture contains synthetic institutions, users, memberships, patients, and one appointment only. Test compares those sentinel records across migration and rerun. No production rows were read. |
| App booking vocabulary | Live booking_appointment_guard accepts routine, first, assessment; the UI and slot finder used followup, first, assessment | Local app now treats routine and followup as the same slot size, stores routine for new follow-up bookings, and normalizes a legacy followup only during an explicitly confirmed reschedule. The live guard itself is not replaced. The migrated PG17.11 fixture exercises app writes/rescheduling and institution/role boundaries successfully. |
| App runtime role | `current_user=postgres`, `session_user=postgres`, search path `ramosolo, public`; `rolsuper=false`, `rolbypassrls=true` | Protected application connection. Schema USAGE/CREATE are true; 30/30 tables have effective CRUD; 29/29 sequences have USAGE/SELECT/UPDATE; 18/18 routines have EXECUTE. Runtime role matches current object owner and new migration objects are also owned by `postgres`; no privilege change is needed for those operations. No grants were changed. |

### Missing objects added by 010

Every row below was absent in the production metadata snapshot. The actual generated SQL creates these objects from historical migrations 007–009, then verifies all current ORM table/column requirements before ledger writes.

| Object | Historical source | Runtime relevance / test evidence |
|---|---|---|
| care_plans | 007 | Dashboard/continuity workflows; ORM columns checked and app dashboard renders. |
| patient_permissions | 007 | Permission-scoped patient data; ORM columns checked; existing permission tests are supporting coverage. |
| clinical_records | 007 | Clinical-record views; ORM columns checked; existing role/record tests are supporting coverage. |
| nursing_observations | 007 | Nursing workflow; ORM columns checked. |
| external_practitioners | 007 | Patient coordination workflow; ORM columns checked. |
| patient_preferences | 007 | Patient preference workflow; ORM columns checked. |
| continuity_events | 007 | Booking and continuity routes query this table when archiving stale events; its absence can break appointment writes independently of calendar tables. ORM columns checked. |
| continuity_history | 007 | Continuity state/history writes; ORM columns checked. |
| continuity_notifications | 007/008 | Consent-bound notification records; ORM columns checked. |
| coordination_policies | 008 | Institution-scoped coordination; ORM columns checked. |
| communication_decisions | 008 | Consent/decision history and new withdrawal hook; ORM columns checked; synthetic outbox/withdrawal guard retained. |
| discharge_followups | 008 | Discharge coordination; ORM columns checked. |
| care_referrals | 008 | Referral workflow; ORM columns checked. |
| referral_clinical_records | 008 | Referral clinical records; ORM columns checked. |
| care_plan_reviews | 008 | Review workflow; ORM columns checked. |
| care_review_signoffs | 008 | Review signoff history; ORM columns checked. |
| coordination_history | 008 | Coordination audit/history; ORM columns checked. |
| coordination_coverage | 008 | Institution-scoped coverage delegation; ORM columns checked. |
| calendar_delegations | 009 | Needed for delegation writes; RLS enabled, owner-only ACL preserved. It does not explain /med/calendar GET by itself. |
| appointment_proposals | 009 | Queried by /med/appointments and /med/calendar; each GET can fail with undefined-table until this exists. Proposal write is exercised after migration. |
| calendar_history | 009 | Queried by /med/calendar and written by booking, rescheduling, blocks, and proposals; app calendar/appointment writes pass after migration. |

## What blocks each observed path

| Path | Evidence-based cause |
|---|---|
| Login | Not blocked by the missing coordination/calendar tables. The user reached an authenticated session. Login reads the existing users table. |
| Medical dashboard (/med) | Its baseline patient, appointment, and admission queries use existing tables. The migrated-fixture login/dashboard read returns 200. |
| /med/appointments GET | The route selects appointment_proposals; this table is absent. |
| /med/calendar GET | The route first selects appointment_proposals and later calendar_history; both are absent. calendar_delegations is not read on this GET and is not its cause. |
| Booking POST | Besides needing the observed availability tables, the path inserts an appointment, writes calendar_history, and calls continuity event archival, which queries continuity_events. Those two missing tables independently block the write. The production trigger also rejects the app's old followup value; the local app compatibility mapping fixes that while preserving the trigger. |
| Calendar delegation POST | calendar_delegations is absent. |

## Draft behavior and safety checks

migrations/010_ramosolo_live_reconciliation_draft.sql is generated by verification/build_reconciliation_draft.py. It does not edit 007–009 and does not drop or replace existing objects. It runs in one transaction with a transaction-scoped advisory lock, lock_timeout='5s', and statement_timeout='5min'.

Preconditions require ledger 1–6; exact baseline table/sequence/function/trigger/column/constraint/index inventories; target-table absence; expected appointment column/constraint/index definitions; no partial attendance-followup upgrade; owner `postgres`; no non-owner grants or matching default ACL; and exact function/trigger hashes and enabled states. Constraint values are encoded as tagged UTF-8 byte-length-prefixed fields (`N;` for null, `V<byte-length>:<text>` otherwise); records are length-prefixed and ordered by the serialized bytes (`COLLATE "C"` in PostgreSQL). The generator and guard now compute the same production fingerprint, `6e42b7f83cb9357f5abc713146cc4d22`. The guard also recognizes one exact fingerprint for the synthetic EDB PG17.11 fixture, whose re-rendered constraints differ only in 16 varchar-to-text array cast placements and two associative-AND parenthesis layouts. Both are complete 165-constraint fingerprints; an altered definition matches neither. The object-by-object production comparison remains the source of truth for the production profile.

Postconditions require all 21 tables, every ORM column, the admission identity index, calendar RLS flags, 34 triggers total, both new trigger/function definitions enabled as expected, unchanged existing trigger/function hashes, expected ownership/ACL state, and unchanged ledger 1–6. Only then does the migration insert versions 7–9 and verify exactly 1–9. A failed precondition, DDL statement, or postcondition aborts the transaction. Rerunning a completed migration fails the ledger precondition before DDL and leaves versions 1–9 unchanged.

The migration does not rewrite historical reminder rows or change application grants. Historical chunks contain the two existing communication_decisions/outbox trigger functions; they execute only on subsequent writes and are tested against synthetic rows. The fixture test verifies no external reminder channel is enabled and that rescheduling cancels the old version before creating the current in-app job.

## Isolated fixture and test results

The fixture is generated from catalog metadata and uses synthetic values only. It reproduces observed columns/defaults, constraints, indexes, sequences, routines, triggers, owners, ACLs, RLS flags, and synthetic sentinels. Its generated SQL is deterministic: constraints are sorted by canonical serialized bytes, and a test compares the PostgreSQL fingerprint to the Python fingerprint. The current PG17 tests execute the actual checked-in migration SQL file.

On isolated PostgreSQL 17.11 (`server_version_num=170011`), all seven requested migration tests passed: startup/CLI rollback and connection reuse, incompatible-state abort, successful apply, schema-drift rejection, mid-flight rollback, postcondition rollback, and migrated-app writes/boundaries. The additional fingerprint regression passed: reordered equivalent catalog input hashes identically, while a changed appointment status constraint is rejected atomically. The test applies the checked-in generated SQL file, verifies the synthetic sentinel survives, checks the ledger and postconditions, and confirms rerun behavior.

The full suite completed with **254 passed, 1 skipped, 3 xfailed** in 478.89 seconds. The one skip is the documented stale demo-seed prototype described below. The EDB Windows PostgreSQL build matches production's 17.11 patch version but is not the Supabase managed platform/build.

The collection failure in `tests/test_demo_seed.py` is explicitly isolated. Both it and `demo_seed.py` are untracked in this checkout, and the prototype depends on 11 absent ORM classes plus absent `Med/MedWebsite/reminders.py`. The test file is retained and calls a module-level `pytest.skip` only while those dependencies are absent. The full suite included that module and reported the documented single skip; no test path was hidden with `--ignore`.

## Remaining limitations

1. Runtime role `postgres` has `BYPASSRLS=true`; no privileges were changed. App institution/role filters are required for current application operations. Any dedicated least-privilege role and RLS-policy change is a separate authorization/security review.
2. The connected read-only project metadata has no backup/PITR fields, and the available Supabase tools expose no backup-list operation. No backup timestamp, retention window, or restore validation was obtained. A current recoverable backup/PITR point and isolated restore check are prerequisites for future production execution.

Read-only app-role query, to run from the actual application's database connection (not a postgres SQL-editor session):

~~~sql
SELECT current_user, session_user, current_setting('search_path') AS search_path,
       current_setting('server_version_num')::integer AS server_version_num,
       has_schema_privilege(current_user, 'ramosolo', 'USAGE') AS schema_usage,
       has_schema_privilege(current_user, 'ramosolo', 'CREATE') AS schema_create;

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

SELECT p.proname,
       has_function_privilege(current_user, p.oid, 'EXECUTE') AS can_execute
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'ramosolo'
ORDER BY p.proname;
~~~
