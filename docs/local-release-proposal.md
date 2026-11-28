# Proposed live release procedure — NOT EXECUTED

Prepared 16 November 2026. This is a gated operator runbook, not permission to
deploy. No live migration, grant/RLS change, notification or deployment was made
during this review. Current local acceptance evidence is in
`verification/acceptance-review.md`.

## Privacy approval and staged activation

Use the [practice decision sheet](privacy-approval-decision-sheet.md) for sign-off
and the [owner checklist](privacy-owner-checklist.md) for evidence. Treat the
older 007–009 rollout example below as historical context. For any separately
approved database change, verify the actual ledger and use the reviewed
reconciliation and runtime-role sequence in the
[security follow-up](ramosolo-security-followup.md).

1. **Confirm recovery before a change window.** Record the current application
   artifact and configuration versions, database ledger and runtime identity,
   and responsibility for pausing writers and workers. Verify an encrypted
   backup or recoverable point, restore access and a successful isolated restore
   rehearsal. Disconnect provider transports in the restore environment.
   Rehearse preserving all appointments, account links, audit and consent
   history, including withdrawals that arrived after a recovery point.
2. **Stage the application with features closed.** Use synthetic data, fake
   mail and disabled SMS, OIDC and appointment email. Leave the booking terms
   approval digest unset. Verify the current draft notice and contact placeholder,
   generic booking enquiry, disabled representative access and absence of
   marketing. Verify HTTPS, no-store, trusted hosts and redacted diagnostics
   at the edge. Review the redacted release scan for the exact candidate.
3. **Activate only individually signed settings.** Publish an approved notice
   and the independently verified request channel together by reviewing
   `policy_info.py` and the policy templates. Reconcile their contents with the
   approved provider and retention decisions before setting an effective date.
   For pricing, validate the versioned JSON against the approved medical
   institution and service categories. Hash the UTF-8 text of the numeric
   institution ID, one LF, then the exact `BOOKING_TERMS_JSON` value with
   `booking_terms.booking_terms_sha256`. Record the digest with the approval.
   Set `PUBLIC_INSTITUTION_ID`, the exact JSON text and
   `BOOKING_TERMS_APPROVED_SHA256` together. A missing or mismatched digest keeps
   terms hidden. The digest binds the deployed values to the recorded approval.
   A changed institution, amount, wording or JSON formatting needs a new digest.
4. **Check each stage before moving on.** On separately authorised staging after
   deployment, open `/book` anonymously and compare the institution, approved
   fee/deposit, currency and all terms against the signed record. Verify fallback
   for unlisted categories and the enquiry-only wording. Check mobile keyboard
   navigation and CSRF. On the notice pages, compare contact, effective date,
   provider and retention statements with the decision sheet. Use a synthetic
   patient and representative account to check that only the patient's own
   information is visible and that direct clinical URLs are denied. Check
   application and approved edge diagnostics with synthetic canaries, and
   confirm that public and protected pages request only first-party resources
   unless an approved integration was intentionally invoked.
5. **Gate any outbound pilot separately.** With fake transports, queue an
   appointment notice, withdraw the permission, then reselect email. The
   old appointment notice must be suppressed and an unrelated security notice
   must remain eligible. Reject marketing at both enqueue and render. Reconcile
   the existing queue before resuming any approved worker. Activate a provider
   only in a separate approved window with its existing enablement, scope,
   verified destination, recipient and quota controls. Keep marketing and
   guardian access disabled. The scope of any future representative pilot
   requires separate software, grant review and authorisation.

If a check fails, stop the affected worker or route and revert the configuration
or previous reviewed application artifact. For pricing, unset the approval digest
and verify the generic enquiry page. For a notice or contact mismatch, restore the
previous approved text or the draft if approval is still pending. Keep withdrawals
and their provenance. A recovery restore must reconcile post-restore-point consent
changes and pending jobs before sending can resume. Avoid requeuing records that
were withdrawn, cancelled or already delivered.

### Representative authority draft for review

Review artifact `supabase/review/representative_authority_draft.sql`, SHA-256
`7653DA9D98C55A03249CF36FA4821D2140EC7A782CB718627AB3F902F7FF9A79`.
Verify the exact bytes with
`Get-FileHash -LiteralPath supabase/review/representative_authority_draft.sql -Algorithm SHA256`.

- **Dependencies.** The private `ramosolo` schema, the `patients (id, institution_id)`
  uniqueness from reviewed migration 017, and the existing
  `memberships (user_id, institution_id)` uniqueness. Review with the migration
  principal that can create the new objects. Include the proposed restricted web
  and worker roles and the standard Data API roles in the grants review.
- **Impact to verify.** The draft creates one empty authority-decision table,
  its identity sequence and indexes. It enables RLS and removes access from
  named service and API roles if present. It contains no data backfill, existing
  table DDL or ledger write. Confirm no effective access from inherited roles,
  schema exposure or publications. Flask-Login remains the application boundary.
- **Preservation rehearsal for separate approval.** The fixture
  `test_reconciliation_migrated_fixture_supports_app_writes_and_boundaries`
  in `tests/test_independent_postgres.py` snapshots existing row projections,
  table owners/ACLs/RLS and ledger values before the draft, then checks equality
  and an empty new table. It also checks cross-institution and clinical-scope
  rejection, inaccessible rows for API/service roles and unchanged Flask
  authorisation. Before staging approval, repeat this on an isolated synthetic
  fixture matching the intended major version and confirm unchanged booking,
  payment and history relationships and active withdrawal safeguards. Store only
  aggregate pass/fail evidence. The prior synthetic run covered the permissions
  and authorisation assertions. The new preservation assertions await rehearsal.

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
connection with `sslmode=verify-full` and the provider CA, the actual
`APP_TRUSTED_HOSTS`, and the matching HTTPS `AUTH_PUBLIC_URL`. Never use a synthetic
test key live. `APP_TRUSTED_PROXY_HOPS=0` is the default; use `1` only behind one
controlled HTTPS terminator that overwrites forwarded scheme and client address, with direct backend
access blocked. Keep `CALENDAR_SYNTHETIC_DELIVERIES` absent from real-data runtime.
Verify the existing approved server dependencies.

For a same-host TLS proxy using Waitress forwarding support, set
`APP_TRUSTED_PROXY_HOPS=0` and use the reviewed peer and trusted headers in the
[security follow-up](ramosolo-security-followup.md).

```text
waitress-serve --listen=127.0.0.1:8000 --trusted-proxy=127.0.0.1 --trusted-proxy-count=1 --trusted-proxy-headers="x-forwarded-for x-forwarded-proto" --call wsgi:create_production_app
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
