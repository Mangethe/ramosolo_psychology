# Proposed live release procedure — NOT EXECUTED

Prepared 16 November 2026. This is a gated operator runbook, not permission to
deploy. No live migration, grant/RLS change, notification or deployment was made
during this review. Current local acceptance evidence is in
`verification/acceptance-review.md`.

## Stop conditions before any live command

1. Reconcile this checkout with the deployed application's richer booking,
   guest, financial and provenance schema. The last protected ledger observation
   was versions 1–6; it was not refreshed in this review. Compare columns,
   constraints, defaults, indexes, triggers and all scheduling writers. `IF NOT
   EXISTS` does not prove that an existing object has a compatible definition.
   Every writer must obey the same doctor-lock and version protocol; otherwise
   the local concurrency result does not protect live scheduling.
2. Obtain practice approval of availability/holiday policies, proposal expiry
   and no-hold rules, delegation, guest verification and communication policy.
   Confirm the card contact/address/service details and the responsible party,
   privacy contact, retention, providers/locations, incident and monitoring
   policies in `docs/privacy-owner-checklist.md`. Current pages are unpublished
   drafts, not an operative privacy notice. Do not publish registration digits.
3. Through the existing protected workflow, identify the deployed runtime role
   and exposed Supabase API schemas. Run the SELECT-only runtime report below
   as that runtime identity, not a management connector. Review least privilege
   separately; do not blindly switch to a nonowner role or enable broad policies.
   These migrations enable RLS on new tables without an application-role policy
   design. Do not alter live grants/RLS under this local authorization.
4. Verify a protected backup and a successful restore rehearsal. Use an
   access-controlled restored environment with email/SMS, payment, referral,
   analytics and external calendar integrations disconnected. Real records and
   backups must never enter this repository or its verification artifacts.
5. Rehearse the exact forward chain on that restored environment. Check
   preservation of existing values/counts and financial/provenance associations,
   outbox triggers, all roles, proposed-time collisions and rollback. Resolve the
   three expected failures in the wider clinical/history requirements before
   claiming that broader reporting scope complete. Approve a release artifact
   and operator maintenance window separately. Stop scheduling writers/workers
   for cutover; keep external delivery disabled throughout.

## Exact migration candidate and impact

Never replay the legacy `lesonto` migrations 001–003 against live `ramosolo`.
For a freshly verified ledger **exactly 1–6**, the proposed order is:

| File | SHA-256 |
|---|---|
| `migrations/007_ramosolo_care_foundation.sql` | `90c33a59d6c7126dd571cc084ffe9a34dc1889627c6a059c38256126616eadbf` |
| `migrations/008_ramosolo_care_coordination.sql` | `ccc29e0d1552f5e121c7a948680260d1c29c74d95d823e469a15ba3f9d7cd443` |
| `migrations/009_assistant_calendar.sql` | `b7ea5efbfed3bf4a24f318bd93d25441e123af2e3aadc0b6cf5cf3cb5196110d` |

007 adds protected care/permission/event records. 008 adds coordination,
consent, referral and review records, optional attendance-follow-up ownership
columns and outbox consent-guard/withdrawal triggers. Existing continuity
notification rows receive suppressed/unverified defaults; do not describe the
entire chain as having no existing-row impact. 009 adds missing appointment
metadata columns, maps existing availability tables and adds calendar delegation,
proposal and history tables. Availability `CREATE TABLE IF NOT EXISTS` clauses
do not retrofit differing existing constraints. Existing appointment IDs,
invoices/payments and provenance are not deliberately replaced or rewritten.
No policy, clinician decision or external delivery is enabled by the chain.

Each file manages its own transaction, advisory lock, ledger precondition and
five-second lock timeout. Do not wrap these files in `psql --single-transaction`.
A failure rolls back that file, not earlier committed files. Inspect the ledger
and stop on failure; never bypass a guard, replay a completed file or edit ledger
rows to force progress.

## Proposed operator commands, only after separate approval

`ramosolo_release` and `ramosolo_runtime` below are proposed protected libpq
service aliases, **not existing configured credentials**. The operator must map
them to the approved target and identities using the existing credential
workflow. Require TLS with certificate/hostname verification where supported.
Do not put passwords/URLs in commands, console output or repository files.

```powershell
Get-FileHash migrations/007_ramosolo_care_foundation.sql,migrations/008_ramosolo_care_coordination.sql,migrations/009_assistant_calendar.sql -Algorithm SHA256
psql 'service=ramosolo_release' -X --set=ON_ERROR_STOP=1 --command='SELECT current_database(), current_user; SELECT version FROM ramosolo.schema_versions ORDER BY version;'
psql 'service=ramosolo_runtime' -X --set=ON_ERROR_STOP=1 --file=supabase/review/security_runtime_readonly.sql
```

Verify target identity and ledger against the approved change ticket, compare
hashes above and capture a protected baseline before continuing. If ledger is
already beyond 6, stop and review the actual state; these are not rerunnable
migrations. Only for the approved, rehearsed 1–6 starting state:

```powershell
psql 'service=ramosolo_release' -X --set=ON_ERROR_STOP=1 --file=migrations/007_ramosolo_care_foundation.sql
psql 'service=ramosolo_release' -X --set=ON_ERROR_STOP=1 --file=migrations/008_ramosolo_care_coordination.sql
psql 'service=ramosolo_release' -X --set=ON_ERROR_STOP=1 --file=migrations/009_assistant_calendar.sql
psql 'service=ramosolo_release' -X --set=ON_ERROR_STOP=1 --command='SELECT version FROM ramosolo.schema_versions ORDER BY version;'
psql 'service=ramosolo_runtime' -X --set=ON_ERROR_STOP=1 --file=supabase/review/security_runtime_readonly.sql
```

Run each command separately and check its exit code before the next. Require
ledger 1–9, reviewed object definitions/privileges and equality of the protected
pre/post base-record and financial/provenance baselines. Do not print patient
rows in a release report. The synthetic PostgreSQL replay is not a substitute
for this restored-schema rehearsal or live preservation check.

## Application deployment candidate and verification

Deploy only the reviewed source and explicitly inventoried public assets; do
not serve/upload the repository root, `.env`, database/backup files, Python,
SQL, logs, docs, verification output, private uploads, source maps or development
directories. There is no frontend build step. Do not overwrite protected server
configuration with a local demo configuration.

Have the operator configure `APP_ENV=production`, `DB_SCHEMA=ramosolo`,
`PYTHON_DOTENV_DISABLED=1`, `FLASK_DEBUG=0`, the protected signing key and database
connection, and the **actual approved** `APP_TRUSTED_HOSTS`. Never use a synthetic
test key live. `APP_TRUSTED_PROXY_HOPS=0` is the default; use `1` only behind one
controlled HTTPS terminator that overwrites forwarded scheme, with direct backend
access blocked. Keep `CALENDAR_SYNTHETIC_DELIVERIES` absent from real-data runtime.
Verify the existing approved server dependencies and run:

```text
waitress-serve --listen=127.0.0.1:8000 --call wsgi:create_production_app
```

Do not expose the development server. The edge must terminate valid HTTPS,
redirect HTTP before sensitive submission, preserve the Host boundary and honor
no-store. Preserve strict-origin referrers and CSRF; do not remove them to fix
proxy behavior. Redact guest-link paths, query strings, bodies and credentials
from edge/WSGI/monitoring logs. Verify no alternate static host or directory index
bypasses Flask's allowlist. Test anonymous and all five roles through actual
HTTPS, direct private-file/debug probes, session expiry, CSRF, caches, denied
records/exports and synthetic browser canaries on the isolated staging target.

Before reopening writes, test concurrent proposal acceptances and competing
bookings/capacity, stale updates, completed history, unchanged invoice links,
consent withdrawal and reminder invalidation using isolated synthetic records.
Prove synthetic records are excluded from any live integration. Check both
desktop/mobile navigation and actual provider links. Obtain the operator's
verification sign-off; then restore approved internal workers only. External
messages/referral transfers remain disabled pending separate authorization.

## Rollback and impact containment

If a migration fails, its transaction rolls back. Keep writers stopped and
inspect which preceding files committed; do not reset the ledger. If the app
fails after successful migration, remove traffic/stop writes and roll back to
the previously rehearsed application artifact. There is no calendar feature
flag assumed here: restrict routes/traffic at the controlled edge or roll back
the app. Retain additive tables/columns, signed plans, consent and calendar
history. Never reset accepted appointment times or recreate cancelled reminders
as an automatic rollback. No destructive down migration is proposed. A database
restore after resumed writes would lose subsequent care/billing changes and
requires a separately approved reconciliation plan, not a blind restore.
