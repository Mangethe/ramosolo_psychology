# Local acceptance review — 16 November 2026

Scope: current assistant calendar, browser-exposure security, medical branding
and privacy pages. Reviewed the implementation and reran synthetic checks rather
than treating earlier implementation reports as proof. No live database,
infrastructure, permissions, delivery or deployment was changed. No credential
file, real patient record or database file was read. This is not certification
of legal, clinical or production readiness.

## Acceptance findings

| Criterion | Result and evidence |
|---|---|
| Authorized future scheduling and alternative times | Local pass: assigned-doctor/patient/institution scope; shared server availability; duration/break/holiday/leave/block/hold/capacity checks; Wednesday outpatient and approved inpatient weekdays preserved. No permissive policy fallback. |
| Patient/guest ownership | Local pass: patient proposal responses require their own active membership/patient scope. Guest opaque links reveal no detail until code verification; swapped code/proposal, wrong code, expiry and consent withdrawal rejected. No real delivery tested. |
| Atomic acceptance | Local PostgreSQL pass: doctor-row transaction lock, refreshed version, same-engine availability and conditional version update. Concurrent duplicate acceptance produces one change; competing intervals/capacity allow one winner. This does not cover alternate live SQL/import/worker writers. |
| Preserve completed history | Local pass: assistant status/proposal/direct-reschedule requests cannot alter completed/no-show/past visits; added a completed-but-future-timestamp regression across all three routes. |
| Reminder replacement and finance links | Local pass: old unsent outbox version cancelled, replacement pending in-app reminder deduplicated; existing appointment ID and synthetic invoice FK/paid amount retained. Real reminder workers/payment tables were not exercised. |
| No browser data/secret/source exposure | Local pass for tested surfaces: synthetic secret/clinical/foreign-patient canaries absent from rendered bodies, CSS, denied responses, cookies and browser storage. Test-client probes also cover crafted role/institution requests, fake sensitive static files, symlinks, errors and exports. This is bounded testing, not a proof about every possible future endpoint. |
| Private files/debug endpoints | Local pass: static allowlist, traversal/dotfile/Python/SQL/backups/uploads/maps/download/debug probes denied; generic errors. Production Host/TLS/proxy/debug checks pass locally. Separate edge/static hosting remains Unverified. |
| Role-aware navigation and responsive shell | Local Chrome pass: anonymous plus patient, assistant, nurse, doctor and admin; all discovered local navigation/footer targets/fragments authorized; desktop 1440×1000/mobile 390×844 bounds, native menus, skip/focus/keyboard table scrolling and reduced motion. See browser artifact below. |
| Practitioner details | Transcription matches the supplied card for Ponky Ramosolo, title/qualification, services and contact/address text. Practice approval and ambiguous postal/contact typography remain Unverified; no registration digits published. Card “Prac. No.” is distinct from HPCSA registration. No claim of independent registration verification. |
| Privacy declarations match code | Local pass as clearly labelled **unpublished 0.1-draft** documents: narrow booking contact acknowledgment, distinct optional consents, scoped access, audit metadata, sandbox/in-app delivery, no chat/AI/analytics in reviewed templates, stated session limits. Hosting/locations, responsible party/contact, retention, recovery, incident handling, caregiver policy and contact hours remain explicitly unresolved. Publication approval is outstanding. |

The added tests and browser fixtures strengthen verification only. No application
permission, CSRF, authorization or business rule was weakened or changed during
this review. Synthetic browser fixtures contain a foreign institution/patient,
protected clinical canary and server-only configuration canary. Network response
bodies are inspected without storing their content in the results artifact.

## Commands actually executed

From the repository root, PowerShell; values below are synthetic, not credentials:

```powershell
$env:PYTHON_DOTENV_DISABLED='1'; $env:APP_ENV='test'; $env:DATABASE_URL='sqlite://'; $env:FLASK_SECRET_KEY='synthetic-coordination-full-suite'; python -m pytest -q
```

Full-suite result: **225 passed, 0 failed, 0 skipped, 3 xfailed, 6 warnings in
473.26 seconds (7m53s)**, exit 0. This includes native local PostgreSQL migration,
role and concurrency tests. Five warnings concern Python 3.12's deprecated
SQLite datetime adapter; one concerns the OneDrive pytest-cache path. Neither
was hidden or fixed by disabling protections.
The suite was collected before the two new regression tests were added below;
those tests were executed separately. Do not add historical run counts.

The three strict expected failures remain explicit unmet wider requirements:
structured diagnosis status/severity/amendment linkage; unknown-date/planned
admission representation; effective-dated facility/practitioner histories and
admission-time medical-aid snapshots. They were not converted to passing tests
or suppressed during this review.

```powershell
$env:PYTHON_DOTENV_DISABLED='1'; $env:APP_ENV='test'; $env:DATABASE_URL='sqlite://'; $env:FLASK_SECRET_KEY='synthetic-acceptance-review'; python -m pytest -q tests/test_calendar.py -k 'completed_history_cannot or guest_verification_code' --tb=short
```

**2 passed, 0 failed, 0 skipped, 27 deselected in 16.88 seconds.**

```text
node verification/check_shell_browser.mjs
```

Initial baseline: **33 checks passed**. After extending response/navigation
coverage: **45 checks passed, 0 failed**, zero external page requests. Both exit
codes 0. Latest machine-readable evidence:
`verification/shell-browser-results.json`; synthetic screenshots:
`C:/Temp/ramosolo-shell-5U8xWf`. Desktop home, mobile assistant menu and mobile
professional draft screenshots were visually inspected on the baseline run;
the extended assistant desktop screenshot was also visually inspected. The
extended run repeats the same rendering plus response checks. The harness
uses an isolated headless Chrome profile and in-memory Flask database, with
non-loopback page requests blocked. No user's normal browser profile is used.

```text
python verification/check_official_policy_links.py
```

Exit 0 means the checker completed, not that every link works: **6 HTTP 200,
0 confirmed HTTP failures, 3 Unverified connection/timeouts** (HPCSA homepage,
iRegister and complaints). Metadata: `verification/policy-official-links.json`.
No TLS validation bypass or practitioner lookup. Regulator links were fetched
directly; external links were not opened from an authenticated patient page.

```powershell
git diff --check -- . ':!node_modules'
Get-FileHash migrations/007_ramosolo_care_foundation.sql,migrations/008_ramosolo_care_coordination.sql,migrations/009_assistant_calendar.sql -Algorithm SHA256
```

Whitespace check exit 0 (CRLF notices only); migration hashes match the separate
proposal. Template/static inspection found no common incorrect HPCSA acronym
variants, client-storage use or production source-map reference. `rg` was not
installed, so PowerShell file enumeration/Select-String was used instead.

## Actual integrations and limitations

Executed: Flask/SQLAlchemy against disposable synthetic SQLite; native local
PostgreSQL 18 migration/role/concurrency fixtures; real headless Chrome against
loopback; unauthenticated public HTTPS resource-link probes. PostgreSQL tests
create their own loopback cluster/databases; no remote fallback is allowed.

Mocked: guest delivery is an in-memory synthetic adapter; reminder replacement
uses synthetic tables shaped from sanitized schema metadata; invoice preservation
uses a synthetic FK sentinel. No SMTP/SMS, external calendar, referral transmission,
payment gateway or live reminder worker was invoked. The preview has no delivery
adapter and its records cannot enter live integrations.

**Unverified:** physical mobile devices, Firefox/Safari, screen-reader speech,
live HTTPS/proxy/cache/static-host behavior, dependency/credential-history audit,
current Supabase exposed-schema settings/runtime identity, fresh schema/provider
region/backups and a restored live-schema rehearsal. Earlier read-only catalog
evidence is historical, not a new live attestation. No live Supabase operation
was needed or performed in this phase.

Remaining release blockers: checkout/live schema and alternate scheduling-writer
reconciliation; protected backup/restore and runtime/edge verification; practice
approval of scheduling/guest/consent rules and professional details; operative
privacy identity/contact and unresolved policy evidence; availability of official
HPCSA links; the three wider clinical/history gaps recorded as expected failures.
Do not count expected failures as fulfilled requirements.

Exact proposed migration/deployment/verification and non-destructive rollback
steps are separately documented in `docs/local-release-proposal.md`. They have
not been executed and require a separate approved live change.
