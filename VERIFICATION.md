# Care-coordination implementation verification — current update

Latest combined calendar/security/branding/privacy acceptance review:
[executed commands and results](verification/acceptance-review.md).
Its actual local Chrome checks supersede the historical browser-host limitations
in earlier sections below. [Proposed live release steps](docs/local-release-proposal.md)
are separate and have not been executed.

16 November acceptance rerun: full synthetic suite **225 passed, 0 failed,
0 skipped, 3 xfailed, 6 warnings in 473.26s**. Two subsequently added guest/history
regressions: **2 passed, 27 deselected in 16.88s**. Extended local Chrome:
**45 checks passed**, zero external page requests. Official-link probes:
**6 HTTP 200; 3 HPCSA connections Unverified**. Exact commands, scope, warnings,
integration limits and remaining release blockers are in the linked review.

Local implementation is complete for the four requested workflows. No live
migration, deployment, permission alteration, message/payment or referral
transmission was executed. Browser checks are **unverified**: the browser-access
host returned unavailable during this turn.

## Final checks actually run

`python -m pytest -q`: **145 passed, 3 xfailed, 6 warnings in 273.83 seconds**
(4m33s), Python 3.14.0. This was a single complete final run with dotenv loading
disabled and an explicit synthetic configuration. It included:

- **27 care-coordination cases:** complete/incomplete discharge planning, actual
  discharge without a plan, duplicate episode prevention and database rejection
  of episode/patient mismatch; owner/cover history, unavailable owner and stale
  updates; attempted versus successful contact and clinician completion;
  incoming/outgoing referral transitions, response dates, cancellation, duplicate
  submission and private clinical-content separation; consent withdrawal after
  queueing, purpose/channel/scope, destination verification and contact windows;
  versioned review sign-off and next-review scheduling; publication plus separate
  patient-sharing consent; every role, cross-patient/institution, CSRF/files,
  operational export, summary-card/drill-down matching, existing outbox preference
  reuse, scheduling-follow-up deduplication and time-limited clinical coverage.
- **17 isolated real PostgreSQL cases:** baseline/forward schema matching,
  version-collision replay, all seven synthetic role variants, booking/check-in/
  acknowledgment races, forward ramosolo 007/008 replay with preserved booking,
  invoice/payment and dataset-manifest sentinels, outbox withdrawal/requeue guard,
  simultaneous referral creation/state change, review sign-off and discharge.
- All existing medical, continuity and permission regressions, plus independent
  metric/export/privacy probes. Assistant admission totals/badges, zero-ID export
  broadening and future-stay counting are now fixed and pass as regular tests.

The three expected failures remain explicit acceptance gaps in the broader
pre-existing diagnosis/admission-history scope: structured confirmed/provisional/
severity/amendment history; unknown-date/planned-admission representation; and
historical medical-aid, transfer and psychiatrist effective-date snapshots. They
are not newly implemented features and are not counted as passes.

Warnings were five Python sqlite3 datetime-adapter deprecations in synthetic
legacy-table fixture inserts and one Windows pytest-cache path warning. They
were not test failures. Earlier focused runs passed 60 checks with the same three
known gaps, six coverage/queue cases, and the isolated PostgreSQL run passed 17
checks before the final full run. Earlier interrupted development runs are not
reported as completed successes. A discharge reassignment autoflush/constraint
failure and the prior assumption that publication supplied sharing consent were
corrected before the final run.

## Implemented behavior and safety boundaries

- Discharge follow-up is unique per admission episode. Actual discharge remains
  possible with missing planning; owner/date/policy are mandatory for clinician
  planning sign-off. Contact attempts and successful contact are recorded without
  completing care; completion is a separate clinician action with outcome and
  closure reason. Reassignment clears planning sign-off. Owner/cover and
  escalation history persist.
- Referral administrative fields and private clinical records are separate.
  Sending never means completed and does not transmit anything. Incoming clinical
  acceptance/decline and final completion require a clinician; administrative
  users may record permitted confirmed external responses and scheduling states.
  Same-patient booking linkage/rescheduling is explicit; no account is created
  for an external service/practitioner. Attachments are not introduced and upload
  attempts on these workflows are rejected.
- Consent history is append-only by purpose/channel/scope, with status, date,
  recorder, method, notice/version, destination verification, contact window and
  timezone. Account creation and publication grant no communication/sharing
  consent. Unverified patient-entered destinations cannot authorize previews.
  Withdrawal suppresses affected unsent previews and pending/failed existing
  in-app jobs; sent history remains intact. Existing explicit reminder opt-ins
  remain bounded to their original patient/verified guest booking context.
- Care reviews have a responsible clinician, actual reviewer/date, private signed
  outcome, next agreed date and sequence history. One pending review per version
  is enforced in the database. A new plan supersedes previous pending reviews,
  preserves sign-offs and does not silently complete anything on GET. Patients
  see the current published projection only with plan-sharing consent; private
  outcomes never enter it. Signed next-review dates are projected without
  rewriting the earlier plan version.
- My actions is a read projection, not another task store or scheduler. It merges
  the source records and existing continuity/scheduling follow-ups without
  duplicating the same reminder-related action. Type/owner/date/status/institution
  filters are shared by cards, drill-downs and operational metadata export.
  Missing owners/dates, overdue/due-soon, unavailability and escalation are text
  labels. Forms use native controls and labels; overflow tables are keyboard-
  focusable and responsive CSS is reused. Manual visual/keyboard QA is unverified.
- Admin assignment cannot confer clinical access. Another clinician needs an
  explicit, time-limited workflow assignment from the primary clinician before
  being eligible as clinical owner/cover. Revocation/expiry removes that access;
  it grants neither general chart/psychotherapy access nor export authority.
  Nurses operate only owned/covered tasks on assigned patients and escalate
  clinical decisions. Sensitive audit entries contain metadata/IDs only.

## Proposed migration and preservation evidence

The protected **read-only** version ledger was rechecked during this change and
still contains `[1,2,3,4,5,6]`. Additional reads were limited to legacy outbox/
preference/follow-up check-constraint definitions; no credentials or actual
patient, invoice/payment, booking-content or dataset-manifest rows were read.

The exact proposed path is:

1. `migrations/007_ramosolo_care_foundation.sql`: nine missing care/permission
   foundation tables in the existing private schema, version 7. No old 002/003
   replay and no booking/financial/provenance replacement.
2. `migrations/008_ramosolo_care_coordination.sql`: nine coordination/history/
   coverage tables, parent identity indexes and matching FKs, optional assignment
   columns on the existing scheduling follow-up, purpose/suppression metadata on
   sandbox previews and guards on the existing in-app outbox; version 8.

Both have exact-ledger guards, transactional/advisory locking and bounded
lock/statement timeouts. `[7]`/`[8]` are proposals: if another migration advances the
ledger, stop and re-review numbering. Public/browser roles receive no new table
or function access. No application runtime grants are assigned automatically.

`verification/coordination-migration-impact.json` records exact SHA-256 hashes,
created-table inventory and impact. The full stage verification and rollback
procedure is in README's **Exact proposed PostgreSQL forward deployment** section.
On SQL error that script rolls back. After success, preserve new tables/histories,
withdrawal guards and cancelled messages when reverting the application; stage
prior-release compatibility with version 8, and use reviewed forward migrations
for any later schema reversal. Never erase ledger versions or consent history.

A synthetic v6 replay verified that appointment, invoice, payment and provenance
sentinels remain unchanged after 007/008. This is not a staging restore or live
financial integration test. The checkout still does not contain the full live
booking/financial/consumer source, including the live required appointment
institution column. Reconcile that application source and verify consumer
transaction/retry behavior before deploying a complete application build.
Financial runtime, Supabase PostgreSQL 17 execution, backup restore and live
transport behavior remain **unverified**. Local PostgreSQL used version 18.

## Clinician/policy and pre-release decisions

The practice must approve deadline/interval and due-soon values, monitoring and
escalation arrangements, who authorizes cover when the primary clinician cannot,
referral acceptance/completion criteria, actual consent notices and collection/
verification methods, healthcare-processing bases/exceptions, patient-facing
wording, history retention and small-cohort/report-audience rules. No default
clinical response times or sharing consent are seeded.

Release remains gated on those approvals, authorized staging/restore and runtime
source reconciliation, browser/accessibility QA and separately reviewed live
migrations. This local implementation provides no production, legal or clinical
readiness sign-off. Synthetic data never entered a live messaging/payment path.

---

# Historical independent review — before this coordination implementation

The following section preserves the prior independent review and original test
counts. Its six-gap baseline is historical: the assistant admission disclosure,
zero-ID export filter and future-current-stay metric have since been fixed as
reported above. Its warning about legacy 002/003 remains valid; the proposed
forward upgrade is now 007/008, not those legacy scripts.

# Independent verification — 16 November 2026

**Release verdict: blocked.** Existing continuity and permission controls pass their
current tests, but that does not establish the broader clinical/admission/financial
acceptance scope. Six strict expected-failure probes document unmet requirements;
they are failures of acceptance, not successful feature checks.

The review used the prior continuity and role-matrix requests as the approved
implementation scope, and this request's scenarios as additional acceptance
criteria. No separate on-disk approved-plan document was found. Application
business logic was not changed during this review; additions are verification
probes, a read-only synthetic preview, metadata evidence and this report.

## Actual executions

| Execution | Observed result | Scope / limits |
| --- | --- | --- |
| `python -m pytest -q` on the existing suite before adding review probes | **88 passed**, 144.31 s | Synthetic in-memory SQLite; existing roles, CSRF, grants, continuity, publication, export and audit tests |
| `python -m pytest -q tests/test_independent_review.py --tb=short -rxX` | **10 passed, 6 xfailed**, 56.25 s | Independent scenario/metric checks; six unmet acceptance conditions remain visible |
| `python -m pytest -v -s tests/test_independent_postgres.py --tb=short` | **13 passed**, 66.88 s | Real isolated PostgreSQL 18, synthetic rows, seven role cases and concurrent HTTP requests |
| `python -m pytest -q tests/test_independent_review.py -k acceptance --runxfail --tb=short` | **6 failed, 10 deselected**, 12.85 s | Release gate: expected-failure handling disabled; all six acceptance gaps reproduced |
| Immutable synthetic preview generation | **12 route snapshots rendered with HTTP 200** | Actual Jinja templates and local CSS, synthetic test sessions, no operational POST endpoint exposed by preview |
| Connected Supabase project/schema inspection | **Read-only metadata verified** | Live PostgreSQL 17.11, `ramosolo` columns/nullability/default-presence and migration version numbers only |
| Desktop/mobile and keyboard inspection | **Unverified** | In-app browser host unavailable; native Computer Use then stopped because current URL could not be established confidently |

There are **111 distinct passing checks across the three main test executions**, plus
**six unmet acceptance probes**. This is not a claim that one combined run had
that result. The assistant-admission probe was subsequently expanded to check
both dashboard and patient-directory output and rerun separately. The final
`--runxfail` command intentionally returns a failing exit status while these
release gaps remain. Structural probes diagnose omissions in the current model;
their column names do not constitute approval of a future schema design.

The first unsandboxed PostgreSQL attempt had 13 setup errors because the new QA
harness put its log inside initdb's required-empty data directory. Logs and data
were separated; the corrected run passed all 13 checks. Earlier sandbox attempts
stalled creating temporary directories and were interrupted. Explicitly approved
local execution resolved that environment limitation. A nonblocking pytest cache
path warning occurred in the successful PostgreSQL run.

## Live schema and migration findings

**Do not apply the new migrations unchanged to the current project.**

- Protected access used the connected Supabase tool. No credential value, `.env`,
  password file, real patient row, invoice row or payment row was read or copied.
- Live metadata reports `ramosolo`, with schema versions **1–6**. The checkout's
  scripts use **`lesonto`** and insert versions **2 and 3**.
- Nine modeled feature tables are absent from the live schema: care plans,
  clinical records, continuity events/history/notifications, nursing observations,
  patient permissions/preferences and external practitioner references.
- The live schema has booking, availability, communication-preference, reminder,
  outbox, invoice and payment-ledger structures absent from this checkout. This
  includes `medical_invoices` and `medical_payment_entries`.
- Live `appointments.institution_id` is required and has no column default, but is
  absent from this checkout's Appointment model. Live trigger semantics were not
  inspected; insert compatibility cannot be assumed.
- Local execution of 001 → 002 → 003 on an empty PostgreSQL database succeeded.
  All ORM table column sets/nullability matched the resulting schema, and a
  synthetic pre-existing institution sentinel was preserved.
- A separate local replay of the observed `ramosolo` name/version ledger
  reproduced a missing-table error with the scripts as written, then a duplicate
  version error after changing only search_path. Transaction rollback preserved
  the synthetic sentinel and ledger and left no partially created care-plan table.
  This replay is not a full clone of live defaults, triggers, extensions or RLS.
- **No live DDL, migration, synthetic seed, cleanup or operational mutation was
  executed.** Forward migration numbering, schema qualification, existing feature
  reconciliation and backup/restore validation remain release prerequisites.

Machine-readable evidence: [schema metadata](verification/live-schema-metadata.json),
[migration ledger/default-presence](verification/live-migration-ledger.json), and
[comparison](verification/schema-comparison.json). These contain structural
metadata only.

## Scenario acceptance matrix

| Requested case | Verified behavior | Remaining gap / verdict |
| --- | --- | --- |
| Multiple confirmed/provisional diagnoses and amended histories | Four separate synthetic diagnosis texts can coexist without rewriting prior rows | **Not structurally implemented:** confirmation status, provisional status, severity and amendment/supersession linkage are free text; no validated current-diagnosis history/filter |
| Missing severity | Generic records do not invent a numeric severity | **Not implemented:** no structured unknown/missing severity field or corresponding reporting denominator |
| Unknown admission dates | Database rejects null `admitted_at`; an existing ongoing stay remains intact after the rejected write | **Unmet:** unknown dates cannot be recorded without fabrication or rejection |
| Facility transfers / psychiatrist changes | Separate historical stays and two practitioner references retain prior values; references create no accounts | **Partial only:** no transfer chain, effective dates, practitioner assignment interval or admission-time practitioner snapshot |
| Changed medical-aid provider | No supported local field/workflow found | **Unverified / absent:** cannot demonstrate historical admission/provider preservation; live financial data was not inspected |
| Repeated admissions / ongoing stays | Closed prior stay plus new ongoing stay remain two rows; current-admitted metric counts one patient | **Partial:** explicit episode/readmission semantics absent |
| Planned readmission | Synthetic future open admission can be inserted | **Fails:** current-admitted count becomes one before its start; no planned-state distinction |
| Missed appointment without relapse | Duplicate no-show handling yields one administrative event, empty clinical definition and no diagnosis rows | **Pass** under approved rule; no clinical inference |
| Patient concern awaiting review | Concern stays `patient_reported` and open; no diagnosis or clinician-confirmed finding is created | **Pass**; review remains manual and monitoring-hours notice remains required |
| Duplicate reminders / failed delivery / resolved follow-ups | Active administrative events and sandbox previews deduplicate; closure retains history; resolved source replay does not reopen; unrelated concern remains open | **Pass for sandbox/staff-recorded workflow only:** no live SMTP/SMS failure/retry transport was exercised |

## Charts, joins and financial separation

All existing displayed metric families were checked: dashboard patient metrics
and continuity category totals/drill-downs. Continuity tests independently
reconstructed expected record IDs and category counts for doctor, nurse, admin,
assistant and peer doctor. Dashboard values were checked against independently
specified completed-visit/stay cases for each staff scope; patient dashboards
contain no staff admission metrics. There are no implemented diagnosis, severity,
facility-transfer, medical-aid or payment charts in this checkout to validate.
There are no such date/facility/provider report-filter controls to test here.

The negative-control diagnosis join produced **8 rows for 2 admission episodes**
when four diagnosis/history texts were joined naively. The implemented current-
admitted metric stayed **1 patient** because it does not join diagnoses. This
proves that existing metric's grain, not the correctness of an unimplemented
admission/payment reporting subsystem.

A separate synthetic PostgreSQL SQL oracle demonstrated payment inflation:
three diagnosis rows joined to payments of 100 and 50 produced **450**, while an
EXISTS-filtered sum correctly returned **150**. This is an aggregation reference
and negative control, **not** a test of an application financial query. This
checkout has no invoice/payment ORM or financial reports to inspect. Its export
resource allowlist does not expose the live invoice/payment tables. Existing
live financial behavior, currency/refund semantics and diagnosis-filtered
financial totals remain **unverified**. Clinical and financial report endpoints,
permissions and output schemas must remain separate when the live modules are
reconciled; do not infer financial correctness from clinical test passes.

## Permissions, exports and small cohorts

Clinical routes/queries/exports were exercised for every role, cross-patient and
cross-institution access, explicit grants, revoked grants, disabled authorizing
clinicians, changed assignment, forged stored grants and patient-ID tampering.
Admins have no default diagnosis/note access and read grants do not permit
clinical authorship. Nurses record observations and perform permitted owned
tasks without diagnostic authority. PostgreSQL tested these role boundaries
against an actual backend, not SQLite's ignored row locks.

Real PostgreSQL concurrency checks verified:

- Two simultaneous patient check-ins create one active alert and preserve the
  second report in history.
- Two competing bookings for the same doctor/slot create one appointment.
- Two simultaneous acknowledgments cause one successful state transition and
  one rejected duplicate, with one acknowledgment history entry.

These are controlled two-request races, not a load test or proof of all races.
Grant-revocation/read races, clinician reassignment races, live outbox claiming,
financial ledger concurrency and high-volume traffic remain unverified.

**Privacy blocker:** the assistant's admission-history route is denied, but the
same assistant still receives `Currently admitted` totals on the dashboard and
an `Admitted` badge on patient-directory rows. A one-patient synthetic cohort
exposes admission status. Evidence is the strict expected-failure probe and
`Med/MedWebsite/templates/medical/dashboard.html:2` /
`Med/MedWebsite/templates/medical/patients.html:1`. No statistical cohort-size
threshold, complementary suppression or differencing protection is implemented.
The practice must distinguish identifiable care-team views from aggregate
reporting and approve an audience/threshold policy before broader reporting.
Authorization filtering alone is not statistical de-identification.

**Export-filter defect:** `patient_id=0` parses as zero, then the truthiness check
at `Med/MedWebsite/controllers/permissions.py:236` skips the requested patient
filter. The response can export all otherwise-authorized patients. It does not
bypass resource/institution grants, but the requested selection is not honored.
Reject invalid/non-positive IDs before constructing any export.

Audit checks confirm record IDs, actor, institution, action and timestamps,
without clinical content. SQL bound parameters are redacted even in tested
integrity errors. Clinical history remains protected record content, distinct
from the operational activity log.

## Live, real local, sandbox and unverified integrations

| Component | Actual verification |
| --- | --- |
| Live Supabase | Connected, metadata-only read; no production application request or data migration |
| Local PostgreSQL | Real PostgreSQL 18 cluster on 127.0.0.1, synthetic databases/users/rows; test databases dropped and server stopped; temporary synthetic cluster files retained outside repository |
| SQLite | Real in-memory database with FK checks; no patient database files opened |
| App authentication in tests | Synthetic Flask test sessions, not live authentication or OAuth |
| Email/SMS | Fixed neutral sandbox previews only; no delivery adapter invoked and no real message sent; staff-recorded failure is not a mocked transport delivery |
| Payments / medical-aid | No checkout payment integration invoked; local SQL oracle only; no live transaction or payment record read |
| Browser | Actual templates rendered into immutable local snapshots; in-app access host failed and native URL-policy stop prevented visual/keyboard checks; preview server stopped |
| CI / deployment | Not run or deployed during this review |

Synthetic cases were confined to isolated databases and the read-only preview.
No synthetic row entered the live outbox, financial ledger or payment integration.
No real data was altered, packaged or included in these evidence artifacts.

## Remaining decisions and release blockers

1. **Migration/schema reconciliation:** use the current `ramosolo` schema and next
   free forward versions, reconcile existing scheduling/outbox/billing models,
   review trigger/default/RLS effects and test an authorized staging restore.
   The new-database success does not authorize applying scripts to the live schema.
2. **Role privacy:** remove assistant admission-status disclosures from all
   aggregate and directory paths; decide small-cohort/report-audience rules,
   exports and complementary suppression before sharing aggregate reports.
3. **Clinical definitions:** approve confirmed/provisional/amended diagnoses,
   severity including unknown, amendment linkage, who can confirm each finding,
   and the distinction between patient/nurse reports and clinician findings.
4. **Admission history:** approve unknown-date handling, planned/ongoing/closed
   states, episode and transfer boundaries, readmission rules, effective-dated
   psychiatrists and admission-time medical-aid snapshots. Future stays must not
   be counted as current. Do not retrofit historical provider values silently.
5. **Financial reporting:** implement/reconcile and independently test existing
   financial modules, permissions, ledger grain, refunds/currency and diagnosis
   filtering without multiplying amounts. No financial correctness sign-off yet.
6. **Export validation:** reject zero/non-positive patient selection and prove the
   resulting export contains exactly the authorized requested records.
7. **Practice operation:** clinician approval of actual monitoring hours, response
   times, warning signs, escalation steps, communication consent and urgent-help
   wording remains necessary; synthetic examples supply no practitioner approval.
8. **Release QA:** desktop/mobile, keyboard/screen-reader behavior, live-version
   staging migration, backup restore, live transport contracts and remaining
   concurrency cases remain unverified. No clinical or production readiness is
   established by the test results.

Verification sources: `tests/test_independent_review.py`,
`tests/test_independent_postgres.py`, and existing role/continuity suites.

## Assistant calendar extension — 16 November 2026

Final executed full command (synthetic configuration; dotenv disabled):

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:APP_ENV='test'
$env:DATABASE_URL='sqlite://'
$env:FLASK_SECRET_KEY='synthetic-coordination-full-suite'
python -m pytest -q
```

**174 passed, 3 xfailed, 6 warnings in 406.04 seconds.** No failures or skips.
The existing expected failures remain unimplemented broader history/reporting
requirements, not passing checks. Five warnings concern the pre-existing SQLite
datetime adapter; one concerns pytest's OneDrive cache directory.

Additional PostgreSQL command, after adding the different-start-time overlap case:

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:APP_ENV='test'
$env:DATABASE_URL='sqlite://'
$env:FLASK_SECRET_KEY='synthetic-independent-review'
python -m pytest -v -s tests/test_independent_postgres.py --tb=short
```

**20 passed, 1 cache warning in 88.66 seconds.** This is an overlapping subset of
the full suite, plus the additional interval-collision case; do not add the counts
as independent tests. The isolated native PostgreSQL server stopped successfully.

The final full collection included 27 calendar-specific synthetic cases. They
cover all five portal roles, cross-institution denied mutations, scoped calendar
views, approved sessions/durations/breaks/holidays/leave/holds/capacity, proposals,
stale forms, delegation, past attendance protection, opaque guest verification,
consent withdrawal, CSRF, and versioned reminder replacement. Existing medical,
continuity, clinical permissions and care-coordination regressions also passed.
PostgreSQL cases verify simultaneous acceptance, different-start interval
collisions, daily capacity and preserved synthetic financial foreign keys.

`git diff --check -- . ':!node_modules'` passed (only a pre-existing CRLF notice).
No node_modules changes were introduced for this work. No frontend build added.

Browser inspection was attempted: the tool returned **browser access host
unavailable**. Desktop/mobile appearance, focus order and interactive keyboard
navigation are **unverified**. Template rendering and CSRF tests passed; those are
not substitutes for browser checks.

Invitation delivery is a synthetic in-memory sink. Reminder tests use synthetic
outbox-shaped tables and never run a delivery worker. Payment checks use synthetic
association sentinels, not a payment provider. No real notification, payment,
external calendar, live migration or production permission change was performed.

The proposed migration is `migrations/009_assistant_calendar.sql`, SHA-256
`b7ea5efbfed3bf4a24f318bd93d25441e123af2e3aadc0b6cf5cf3cb5196110d`.
It requires separately reviewed 007/008 before 009. Current protected metadata
inspection and prior ledger evidence identify live versions 1–6; no migration
was applied. Synthetic forward replay preserves existing values, financial and
dataset-provenance sentinels. A restored live-schema rehearsal remains required.

See [workflow, setup, policy decisions, migration impact and rollback](docs/assistant-calendar.md),
[detailed verification](verification/calendar-review.md) and
[migration manifest](verification/calendar-migration-impact.json).
Release remains blocked by checkout/live scheduling divergence, unreviewed
alternate scheduling writers, unapplied migration chain, practice approval of
proposal/delegation rules and unverified browser/live integrations.

## Focused browser-exposure security review — 16 November 2026

Latest executed full suite, after the security implementation:

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:APP_ENV='test'
$env:DATABASE_URL='sqlite://'
$env:FLASK_SECRET_KEY='synthetic-coordination-full-suite'
python -m pytest -q
```

**201 passed, 3 xfailed, 6 warnings in 598.21 seconds. No failures or skips.**
The three previously documented broader clinical/admission/history expected
failures remain unresolved; they are not passing security or reporting checks.
Warnings: five pre-existing SQLite datetime-adapter deprecations and one pytest
OneDrive cache-directory warning.

Focused command:

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:APP_ENV='test'
$env:DATABASE_URL='sqlite://'
$env:FLASK_SECRET_KEY='synthetic-security-review'
python -m pytest -q tests/test_security.py --tb=short
```

**26 passed in 47.49 seconds.** These cases are included in the full total and
must not be added to it. Anonymous, patient, assistant, nurse, doctor and admin
requests exercise direct URLs, crafted role/institution/patient IDs and exports.
Synthetic canaries cover response source, configuration disclosure, fabricated
private/source/static files, symlink/traversal attempts, errors/logs, HTML escaping,
decoded session cookies and clinical submissions. Real login, idle/absolute expiry,
legacy remember-cookie rejection, tampered cookies, valid/missing CSRF, cross-origin
POSTs, HTTPS, trusted hosts/proxies, debug and database TLS settings were tested.
All existing role/business/concurrency tests also passed.

`git diff --check -- . ':!node_modules'` passed; only CRLF conversion notices.
No frontend build, obfuscation, right-click/F12 blocking or live deployment added.

Protected read-only Supabase catalog queries confirmed 30 private-schema tables,
all owned by postgres and with RLS disabled, while anon/authenticated/service_role/
authenticator lack schema USAGE and private table data access. No live grants/RLS
changed. The deployed Flask runtime role and control-plane exposed-schema list
remain unverified; connector identity is not runtime attestation. A SELECT-only
runtime review script and separate live proposals are documented.

Actual browser inspection was attempted and returned **browser access host
unavailable**. DevTools View Source/Inspect/Network/storage checks at the real
deployment, edge/static aliases, CDN caching, HTTPS/proxy topology and production
log redaction remain outstanding. Test-client response and download checks do not
claim browser or edge verification. No real secrets, secret files or patient data
were read or copied. No live messages, payments or configuration changes occurred.

See [confirmed findings, fixes and deployment checks](docs/security-review.md),
[sanitized database metadata](verification/security-supabase-metadata.json) and
[SELECT-only runtime-role checks](supabase/review/security_runtime_readonly.sql).

## Public website and portal shell — 16 November 2026

Final full regression command, with dotenv disabled and synthetic configuration:

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:APP_ENV='test'
$env:DATABASE_URL='sqlite://'
$env:FLASK_SECRET_KEY='synthetic-coordination-full-suite'
python -m pytest -q
```

**213 passed, 3 xfailed, 6 warnings in 886.85 seconds. No failures or skips.**
The three earlier broader history/reporting expected failures remain; they are
not passing checks. Warnings remain five SQLite datetime-adapter deprecations
and one pytest OneDrive cache-directory warning. This includes the 12 new shell
cases and all prior security, permission, medical, coordination, migration and
native local PostgreSQL concurrency tests.

Initial targeted command:
`python -m pytest -q tests/test_shell.py tests/test_medical.py tests/test_security.py --tb=short`
passed **81 tests in 171.39 seconds**, before the real-browser referrer correction.
Do not add this overlapping total to the full-suite count.

Final browser command: `node verification/check_shell_browser.mjs` — **27 checks
passed**, using installed headless Chrome, Node core APIs, a loopback in-memory
synthetic Flask server and an isolated temporary browser profile. No new QA
dependency or frontend build was installed. Both processes terminate after QA.
External page requests were blocked; the final result recorded **zero**.

Verified at 1440px desktop / 390px mobile: public home/form/privacy/inpatient/login
layout bounds; all five medical-role workspace bounds; native menu Enter/Tab;
skip-to-main; reduced-motion preference; normal CSRF login/logout; accessible main
landmark; and keyboard horizontal table scrolling with ArrowRight. Seven synthetic
screenshots were captured, and public/assistant desktop/mobile/menu/table screens
were visually inspected. Latest manifest: `verification/shell-browser-results.json`.
The final screenshot folder is `C:/Temp/ramosolo-shell-zWb1UN`, outside public hosting.

Real browser testing discovered that the earlier global `no-referrer` header
caused Chrome to send `Origin: null` for valid form navigations. The response
policy is now **strict-origin**, which withholds paths, queries and opaque tokens
while allowing normal origin/referrer validation. CSRF, HTTPS CSRF checking and
cross-site POST rejection remain enforced. The real login/logout flows passed
for patient, assistant, nurse, doctor and admin after the correction; unit tests
assert the revised header. This supersedes the previous local-browser-unverified
status for the checks listed above, not for the production edge or physical devices.

The actual repository had no navbar/footer/chat partials initially; existing flash
and table partials were reused. User-pasted navbar/footer markup was adapted to
working medical endpoints. The chat reference was not included or connected.
Existing title/content blocks remain; CSS/font/script inspection found no runtime
framework, font imports or script bundles to deduplicate. System fonts and one
local stylesheet remain. Framework CSS hooks, if later used, precede overrides.

Confirmed user-supplied spelling **Ponky Ramosolo** is used. The business-card
images and reference base/stylesheet remain unavailable. Exact professional title,
services, address, contact digits, practice number and HPCSA registration were
**not transcribed, invented or independently verified**. Older conflicting public
details were removed and confirmation remains required before publication.
Practice/HPCSA numbers remain separate pending facts. No operating hours invented.

Unverified: physical devices, Safari/Firefox, screen-reader announcements, exact
missing-reference fidelity and production HTTPS/CDN/proxy behavior. The linked
privacy information remains a draft, pending practice-approved notices in the next
phase. No deployment, live migration, grant/RLS change or real communication occurred.
`git diff --check -- . ':!node_modules'` passed with only CRLF notices.

See [implementation, source status and remaining publication requirements](docs/public-shell.md).

## Draft privacy, data-management and professional information — 16 November 2026

Implemented local, read-only `/privacy-notice`, `/data-management` and
`/professional-information` pages, the `/governance` index and footer links.
All display **0.1-draft**, an explicit unpublished status and an unset effective
date. Legal responsible-party identity and approved privacy contact are pending;
no Information Officer is invented or appointed. The booking checkbox still
covers contact about the enquiry only, now linking the draft notice and explicitly
excluding marketing/referral-sharing enrolment. Booking validation/persistence,
authorization rules, models and schema were not changed.

Executed with dotenv disabled, APP_ENV=test, DATABASE_URL=sqlite:// and a synthetic
signing key:

```text
python -m pytest -q tests/test_policy_pages.py tests/test_shell.py tests/test_security.py tests/test_coordination.py --tb=short
```

**77 passed, 5 pre-existing SQLite datetime-adapter warnings in 137.33 seconds.**
No failures or skips in the final targeted run. Includes all five roles plus
anonymous policy access; no canary/private-data disclosure; CSRF and read-only
methods; source attribution and withheld registration digits; unknown hosting/
backup/retention fields; footer/official links; narrow booking agreement with
crafted optional-consent fields; and existing purpose/channel withdrawal and
queued-notice suppression regressions. An initial 50-case run had one incorrect
test expectation for POST to a GET-only route (actual 405, not CSRF 400). The
expectation was corrected; no protection was disabled. Booking POST without CSRF
still fails. The full suite was not rerun for these read-only content/routes;
the previous 213-pass/3-expected-failure full result is historical, not added here.

`node verification/check_shell_browser.mjs`: **33 checks passed**, zero external
page requests. New pages were checked at desktop 1440px/mobile 390px for layout
bounds and visible unpublished status; existing all-role login/logout, menu/focus,
reduced-motion, skip-link and table keyboard checks passed. Policy desktop and
professional mobile screenshots were visually inspected. Latest synthetic image
folder: `C:/Temp/ramosolo-shell-ou67Pw`; manifest:
`verification/shell-browser-results.json`. Physical devices, other browser engines,
screen-reader announcements and the live HTTPS edge remain unverified.

Two supplied card images were read directly. Professional title/qualification,
services and general contact/address fields are attributed to that material, not
independently verified. The apparent street spelling and contact digits remain
confirmation items. The card's **Prac. No.** is not an HPCSA registration. No practice
or HPCSA registration digits are included in public constants/pages; the full card
image was not copied into public assets. No operating/contact hours were invented.
Public templates were checked for common incorrect HPCSA acronym variants; none
remained. General card contacts are not described as approved privacy contacts.

Official source checks used the Information Regulator complaints, POPIA forms,
PAIA guidance, eServices and security-compromise resources. A public HTTPS checker
was rerun with approved network access after sandbox connection failure. **Six
Regulator URLs returned HTTP 200.** HPCSA homepage/iRegister/complaints resources
were identified on the official domain, but direct retrieval remained unavailable;
**three HPCSA connection checks are unverified**. No TLS validation was bypassed,
practitioner lookup made, credentials used, form submitted or officer registered.
See `verification/policy-official-links.json` for URL/status/redirect metadata.

The current controllers, models, security/access/consent/scheduling code, templates,
test workflow and earlier sanitized Supabase schema/security snapshots were
reviewed. A fresh protected project/provider query failed during OAuth token
refresh; no live provider region, processing/support/backup location, backup plan,
runtime role, operator contract or incident process was inferred. No `.env`,
real credentials, patient records or database files were read. No live message,
migration, infrastructure, grant/RLS or regulatory change occurred.

`git diff --check -- . ':!node_modules'` passed (only CRLF notices).
[Owner approval/evidence checklist](docs/privacy-owner-checklist.md),
[application/infrastructure evidence](verification/policy-evidence.json) and the
pages keep unresolved policy decisions separate from implemented behaviour.


## Booking/login bundle application — 17 November 2026

Reviewed and applied `booking-login-fix/booking-login-fix.patch` after a successful
`git apply --check`. All six applied files match the supplied replacements.
Existing/concurrent local ignore-file changes and the extracted bundle were left
untouched. Updated schema-default documentation and restricted pytest discovery
to application `tests` to avoid collecting duplicate reference-bundle tests.

Full synthetic suite: **241 passed, 0 failed, 0 skipped, 3 xfailed, 6 warnings in
414.01s**. Bundle module: **14 passed in 9.49s** (included in the full count).
Isolated Chrome: **45 checks passed**, zero external page requests. Standalone
read-only diagnostic against intentionally empty in-memory SQLite correctly
returned exit 1 with missing objects; initialized synthetic CLI checks passed.
The first full attempt stopped with one duplicate-reference collection error;
this was resolved by `pytest.ini`, without excluding application tests.

Exact commands, patch hash, limitations and preserved changes:
[booking/login review](verification/booking-login-fix-review.md).
No protected credential file, actual patient/database file or real account was
read/tested. No live database change, service restart, migration, seed or deployment.
