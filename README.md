# Ramosolo · Le Sonto Medical

A lightweight Flask practice website and medical workspace, extended from the
uploaded Ramosolo psychology starter. Server-rendered Jinja templates and local
CSS; no frontend framework, build step, CDN, JavaScript dependency or Supabase SDK.

**Local development prototype. Use synthetic data until deployment, privacy,
practitioner content and operational controls have been reviewed.** The supplied
practice name, contact details, services and address came from the original
starter; qualifications and facility relationships have not been independently
verified. Exact operating hours were not supplied, so the website asks visitors
to confirm availability by phone.

## Run on Windows (PowerShell)

Extract this folder, open a terminal in it, then:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m flask --app app:create_app seed-demo
python -m flask --app app:create_app run
```

Open `http://127.0.0.1:5000`. The seed command prints a **random demo password**;
keep it locally. The password is not committed or included in this archive.
Demo users:

| Email | Role / view |
| --- | --- |
| `admin@ramosolo.example` | Administrator for the demo medical institution; education placeholder membership |
| `dr@ramosolo.example` | Doctor, assigned patients and practice counts |
| `nurse@ramosolo.example` | Nurse, explicitly assigned care and admissions |
| `dr_assist@ramosolo.example` | Assistant, supervising doctor's scheduling and patients |
| `patient@ramosolo.example` | Patient, own appointments and seven-day reminders |
| `dr2@ramosolo.example` | Second doctor, separate patient cohort |

All seeded people and clinical operations are fictional. The seed command only
runs on an empty local SQLite database and does not overwrite existing data. No
account or database is bundled. `init-db` creates empty local tables instead.
Use a dedicated local database if you want to reseed; never delete live data.

## Roles and institution boundaries

An account can have memberships in multiple institutions, with **one role per
institution**. Switch through Institutions. Each request reloads the current
membership from the database; changing a URL or hiding a menu is not the access
control. There is no public role selection or self-registration.

| Capability | Doctor / psychologist | Nurse | Doctor assistant | Patient | Admin |
| --- | --- | --- | --- | --- | --- |
| Operational patient/contact records | Assigned | Assigned | Active supervisor's patients | Own appointments | Current institution |
| Bookings and administrative follow-ups | Assigned | View; complete own assigned tasks | Supervisor's cohort | Own appointments only | Current institution |
| Admissions/facilities operations | Assigned | Assigned | No admission history | No | Current institution |
| Diagnose, author clinical notes/events/plans | Assigned clinician only | Never | Never | Never | Never |
| Care-plan and concern/clinical-event reading | Assigned | Separate clinician grant per resource/patient | No | Approved patient-facing plan only | Separate clinician grant per resource/patient |
| Diagnosis/clinical-note reading | Assigned | Separate clinician grant per resource/patient | No | No internal records | Separate clinician grant per resource/patient |
| Psychotherapy notes | Assigned | No | No | No | Separate explicit grant |
| Nursing observations | Read assigned | Author/read own; other observations require grant | No | No | Separate explicit grant |
| Clinical task acknowledgment/completion/escalation | Assigned | Read grant plus task ownership | No | No | No; clinical grants are read-only |
| Patient check-ins/preferences | Review assigned concerns | Concern read grant required | No | Own, optional; never clinician-confirmed automatically | Concern read grant required |
| Grant/revoke patient permissions | Assigned clinician only | No | No | No | No |
| Exports | Assigned records | No | No | No | Explicit export grant plus resource read permission |
| Accounts and operational administration | No | No | No | No | Current institution |

The executable matrix and deny-by-default resource scopes are in `access.py`.
**Roles & permissions** is available in the portal before opening care modules.
An admin's institution-wide operational access does not grant clinical reading.
Clinical resources have separate scopes; a clinical read grant never grants
clinical authorship. Unknown roles, permissions, record types and export resources
fail closed. There is no global superadmin web account.

From an assigned patient, the clinician opens **Explicit patient permissions**
and grants or revokes individual resources for an active admin or assigned nurse.
Permissions bind institution, patient, active membership and current treating
clinician. A disabled authorizing clinician, changed treating doctor, revoked
membership, revoked grant or removed nursing assignment removes the corresponding
access on the next request. Account administrators cannot issue these grants.
Doctor assistants and patients cannot receive internal clinical grants.

Nurses need an explicit clinical-resource read grant and must own a follow-up to
change its clinical task status. After escalation transfers ownership to the
clinician, that nurse can no longer complete the task. Nursing observations and
escalation flags remain separate records; they never create diagnoses or clinical
events. Diagnoses, clinical notes and psychotherapy notes are append-only records
requiring the assigned clinician's explicit authorship confirmation.

Sensitive views, chart totals/drill-downs and POST-only CSV exports use the same
patient/resource scopes. Admin exports require a separate patient-specific
`export` grant as well as each clinical read grant. Operational exports include
contact fields only. CSV formula-like values are escaped. Activity records store
actor, institution, resource ID, action and timestamp, without clinical content.
SQL parameter logging is suppressed, including exception parameter rendering.
Clinical history remains in its protected clinical records rather than activity logs.

Institution creation and verified cross-institution membership are owner CLI
operations. Suspending a membership removes that institution's access without
suspending unrelated memberships. A disabled doctor supervisor removes the
assistant's patient scope. Nurses require explicit care assignments; assignment
alone issues no clinical grant.

`education` is a supported institution type and a clearly labelled placeholder,
not a finished education portal. Education memberships cannot access medical
routes. No learner records or education workflows are implemented.

## Implemented medical workflows

- Public details, services, address, contact links, hours-by-enquiry and appointment requests.
- Login and separate dashboards/navigation for the five requested roles.
- Distinct active, inactive, never-seen and currently admitted patient counts.
- Patient list/search and individual operational histories, within assignment scope.
- Create patients; admin creates a portal account and explicitly links an existing
  patient or creates a new one. Email matching never automatically grants access.
- One-hour appointments on the hour; database-enforced doctor/patient slot conflicts.
  Cancelled appointments release their slot. Staff can update appointment status.
- One open admission per patient; discharge preserves admission history.
- In-app reminders derived from upcoming scheduled appointments in the next seven
  days. No SMS, email, calendar synchronization or background message sending.
- Admin booking-request inbox: contact the requester, create/select the patient,
  and schedule a confirmed appointment separately. Marking reviewed is not confirmation.
- Account provisioning/suspension, nursing assignments, institution switching and
  a basic activity log for mutations and individual staff patient-record views.

### Supportive care continuity

The medical navigation now includes a **Follow-up queue** for staff and an
**Optional check-in** page for patients. Doctors open **Care plan** from an
assigned patient or the queue. Only the assigned doctor authors and approves
plan versions. Assigned nurses and admins need explicit patient-specific read
grants for each clinical resource. Doctor assistants see administrative follow-ups
only. Patients cannot open staff queues or internal care-plan records. The clinician
can explicitly publish the agreed patient-facing plan; its SQL projection omits
internal definitions, clinical-event rules, diagnoses, notes and staff history.
The latest plan must be published; old versions are not shown as a substitute.
Patients can separately record their contact/consent preferences. Declining consent
or removing a channel restricts sandbox previews immediately and does not change
appointments or treatment. New channels do not broaden the clinician-agreed consent.

External treating psychiatrists are patient-scoped **references**, managed by the
assigned clinician and readable only through the corresponding clinical scope.
Recording their name, contact and registration reference creates no login account,
membership, invitation or notification.

Each plan records patient-agreed goals and individual warning signs, preferred
channels and an explicit communication-consent choice, planned appointments,
review date, an enabled assigned clinical owner, response/escalation steps,
practice-approved urgent-help instructions, actual monitoring hours (including
time zone and holiday arrangements), and the practice's clinical definitions.
Saving requires the clinician's attestation of patient agreement and practice
approval. Earlier versions remain available. No practice hours, definitions,
urgent-help wording or response times are invented or seeded.

Enter an approved response time for each enabled event rule. Blank means
disabled. Times are **elapsed minutes from event recording**, including outside
monitoring hours; clinicians must choose values matching the agreed service.
Existing follow-ups retain their original deadline and plan snapshot when a new
plan is agreed. Updating the plan does not silently change an existing task's
owner, treatment or response time; staff can explicitly reassign an active task.

Three separate event categories are stored and constrained in the database:

- **Administrative:** missed appointment, unconfirmed booking, failed reminder,
  overdue follow-up. A staff no-show update opens a missed-appointment follow-up
  only if the current plan enables it. Other administrative events are recorded
  explicitly; appointment references must belong to the scoped patient, and an
  overdue review requires the plan's review date to have passed. Unconfirmed
  booking and failed reminder records are staff observations, not inferred delivery
  failures. Unlinked public booking enquiries remain in the admin booking inbox.
- **Patient-reported:** optional contact request or agreed check-in. Patients see
  only practice-entered monitoring hours and urgent-help instructions before
  submission, with an explicit notice that submissions are not continuously
  monitored. Without an enabled agreed rule, submissions remain unavailable.
- **Clinical:** deterioration, lapse or relapse, explicitly entered by the
  assigned doctor with confirmation that the practice's recorded definitions
  apply. Administrative events never generate a clinical event or diagnosis.

Active alerts are deduplicated by patient, event kind and source. Additional
patient and clinician reports append history without postponing the deadline.
The queue shows owner, due time, reason and state. Staff record acknowledgment,
contact attempts (including channel/result), outcomes, agreed escalation,
assignment, closure and archiving, with actor and timestamp history. Overdue
tasks are highlighted for staff review. There is no background monitoring worker
or automatic escalation; the practice must staff the queue during the entered
hours. Closure/archive history is a separate queue view.

Explicit appointment status resolution and rescheduling archive linked obsolete
administrative alerts. Rescheduling preserves the original appointment and
creates a replacement atomically; conflicting slots roll back the change.
A newly agreed plan archives obsolete review-date alerts. No continuity rule
cancels care, changes treatment or restricts portal access.

**Notifications are sandbox previews only.** No external delivery adapter, real
message sending or recipient address is used. A preview requires the latest
plan's communication consent and an agreed channel, uses fixed neutral wording,
omits diagnoses and patient content, and is deduplicated per event/channel.
No automated diagnosis, medication recommendation or risk probability is provided.

The current protected `ramosolo` schema already has versions **1–6**. The proposed
forward path is **007 → 008**, described below. Files 001–003 remain historical
new-database/test fixtures; **do not apply 002/003 to the existing ramosolo ledger**
or rename them as an upgrade. No live migration is applied automatically.

These workflows are a development prototype and require practitioner and
operational review; no clinical effectiveness or production readiness is claimed.

### Patient counting rule

The last `completed` appointment at or before the current time determines the
patient status. Exactly 90 elapsed days is **active**; greater than 90 days is
**inactive**. No eligible completed visit means **not yet seen**. Future visits,
no-shows and cancelled appointments do not count. Counts are distinct patients,
not appointments. Current admissions have no discharge timestamp and are counted
independently of activity. UTC is stored; dates/times display in
`Africa/Johannesburg` (SAST). The 90 days are elapsed time, not calendar-day truncation.

## Supabase PostgreSQL

This version uses **Flask-Login as the single authentication authority** and
Supabase as PostgreSQL hosting. It does not create Supabase Auth identities or use
browser Data API access. Do not mix Supabase Auth JWTs with these Flask sessions.
The original `.env` was deliberately not read or copied. The original
`SUPABASE_URL` / `SUPABASE_KEY` settings are not consumed by this implementation.

1. Use a new test database/schema first. The baseline is in
   `migrations/001_initial_postgres.sql`. Review it before running it through an
   authorized PostgreSQL connection. It creates the private `lesonto` schema;
   it does not touch an original `public.appointments` table or import old requests.
2. Keep `lesonto` outside Supabase's exposed Data API schemas. The baseline revokes
   access from `PUBLIC`, `anon` and `authenticated`; browser keys cannot query it.
3. From Supabase **Connect**, copy the direct or session-pooler PostgreSQL URL
   appropriate for your server. Set `DATABASE_URL` in your private environment.
   SQLAlchemy uses `postgresql+psycopg://`; ordinary `postgresql://` URLs are also
   normalized. URL-encode password characters and configure SSL. For server
   identity verification use `sslmode=verify-full` and the appropriate root certificate.
4. `DB_SCHEMA` now defaults to `ramosolo` and must match the applied migration.
   Set `DB_SCHEMA=lesonto` explicitly for the historical baseline described above;
   do not replay it on existing hosted data. Use a
   dedicated runtime database role with only required DML/sequence privileges,
   separate from the migration owner; do not expose its password to a browser.
5. Set a random `FLASK_SECRET_KEY` of at least 32 characters. Production requires
   `APP_ENV=production`, PostgreSQL, SSL connection configuration and HTTPS for
   session cookies. The presence of `sslmode` alone is not a certificate audit.
6. Bootstrap an institution and account from the trusted server terminal:

```powershell
python -m flask --app app:create_app create-institution --name Ramosolo --kind medical
python -m flask --app app:create_app create-admin --institution-id 1
```

Use the actual returned institution ID; it may not be 1. `create-admin` prompts
for the name/email/password. Admin then provisions staff and patient accounts.
Set `PUBLIC_INSTITUTION_ID` to route public appointment requests to that medical
institution. Without it, the first medical institution is used (local convenience).
For multi-practice deployment choose it explicitly.

For existing accounts, an authorized owner can run `add-membership` after identity
verification; patient/assistant roles require `--doctor-id` in the same institution.
`reset-password` prompts for a new password, resets a temporary login lock, and
invalidates existing sessions by changing a session version. No reset email is sent.

**Live Supabase connectivity and the PostgreSQL baseline have not been executed
against your account.** Tests use local SQLite with foreign keys enabled. A live
PostgreSQL integration check is required before deployment. This baseline initializes
new storage, not an automatic migration of any previous Le Sonto database. Future
schema changes need separately reviewed numbered migrations.

Official setup references:
- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://flask-wtf.readthedocs.io/en/1.2.x/csrf/
- https://flask.palletsprojects.com/en/stable/web-security/

## Structure

```text
app.py                        Flask application factory
config.py                     Environment and server settings
extensions.py                 Database, sessions, CSRF
access.py                     Shared institution / patient scope policy
auth.py                       Login and logout
administration.py             Users, roles, requests, institutions, activity
medical_services.py           Counts, time conversion, service options
continuity_services.py        Approved continuity rules, deduplication and history
cli.py                        Local seed and owner provisioning
Med/MedWebsite/controllers/    Public and medical routes
Med/MedWebsite/templates/      Medical views
Edu/                          Explicit education placeholder
models/                       Core, RBAC, medical, education placeholder, governance
templates/                    Shared, auth, users, institutions, admin, public views
static/css/                   Local stylesheet, no frontend dependencies
migrations/                   PostgreSQL baseline and care-continuity upgrade
tests/                        Automated permissions and behavior checks
```

## Verify

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

See `VERIFICATION.md` for the observed results and remaining checks. These tests
are not a regulatory assessment or target-device accessibility audit.

## Before any real patient use

This is an implementation starter, not a claim of POPIA/HPCSA compliance or a
production clinical record system. Have the practice review the public details,
service wording, privacy notice, retention rules, informed consent and admissions
workflow. Confirm actual operating hours instead of inventing them.

Complete live PostgreSQL tests, backup/restore checks, HTTPS deployment, account
recovery and invitation delivery, real user/device/accessibility tests, monitoring,
edge rate limiting and bot/spam controls. Password login has per-account temporary
lockout; it is not a substitute for network-level throttling or MFA. Concurrent
high-volume workloads and full appointment calendars are outside this starter.
Appointments use fixed one-hour slots; configurable durations and backdated
admissions/discharges would be separate changes. Public enquiries are not emergency
communications. The activity log is a basic application record, not an immutable
compliance audit trail, and is not a complete log of every list view.

Run development only on loopback. For a reviewed deployment use a WSGI server such
as `waitress-serve --call app:create_app`, behind a configured HTTPS reverse proxy.
Do not expose the Flask development server or demo database publicly. License and
content reuse rights remain the owner's decision; no license was invented.


## Connected care coordination

**My actions** is the medical workspace entry point. It projects discharge,
referral, care-review, existing continuity and existing scheduling follow-up
records. There is no second task table, scheduler or notification outbox. Each
source appears once; existing scheduling follow-ups take precedence over a
matching continuity alert, and care-review records replace duplicate review-date
alerts in the combined view. Opening pages writes audit metadata only.

### Local setup

For a new synthetic local database, use an explicit local configuration rather
than loading a private deployment configuration:

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:APP_ENV='test'
$env:DATABASE_URL='sqlite:///coordination-synthetic.db'
$env:FLASK_SECRET_KEY='synthetic-local-only-not-for-deployment'
python -m flask --app app:create_app init-db
python -m flask --app app:create_app seed-demo
python -m flask --app app:create_app run
```

For an existing **synthetic SQLite** prototype, explicitly run
`upgrade-permissions` followed by `upgrade-coordination`. These add missing
publication/preview columns, source tables and identity indexes; they grant no
consent or clinical access and publish no plan. Historical sandbox previews
without purpose-specific evidence become suppressed. Do not point QA commands
at live databases. The upgrade commands reject PostgreSQL/production; PostgreSQL
uses the reviewed SQL files below. Nothing seeds clinical policies implicitly.

### Roles and day-to-day workflow

| Role | How to use coordination |
| --- | --- |
| Assigned doctor / psychologist | Approve deadline policies; sign off episode follow-up planning; confirm completed follow-ups; author private referral content and record clinical referral decisions; sign actual care reviews and next agreed dates; authorize time-limited covering clinicians. |
| Nurse | Open My actions for explicitly owned/covering tasks on assigned patients; record contact results, observations and escalation. Successful contact does not sign off clinical follow-up. Private review/referral notes require the existing explicit clinical-note grant. |
| Doctor assistant | Create/track administrative referral records, confirmed external response/scheduling states, existing scheduling follow-ups and permitted consent collection. No discharge clinical decisions, private notes or review sign-off. Incoming clinical acceptance/decline requires a clinician. |
| Admin | Institution-wide operational queue, owner/cover/deadline assignment and consent administration. Assignment does not grant clinical authority; private content still needs explicit patient permissions. Cannot issue clinical coverage or sign reviews/completion. |
| Patient | Own explicitly shared agreed actions, current published care-plan projection, appointments, optional check-ins and purpose-specific preferences. Private notes/sign-offs and internal referral content are excluded. No family/caregiver access is inferred. |

**Discharge.** From Admissions, open an episode's follow-up planning link. Actual
discharge remains possible without a plan: it records the discharge and leaves
an unassigned, undated, incomplete follow-up action. Historical discharged
admissions without a follow-up also appear as missing-planning actions without
GET-created records. A clinician-approved discharge policy, accountable owner
and due date are required for planning sign-off. An approved policy can supply a
deadline when the owner is known; the clinician may record a case-agreed date.
Changing the assignment/date invalidates planning sign-off until reviewed.
Contact attempts have neutral result codes. Reached/successful contact becomes
`contacted`; only explicit clinician completion records the outcome and closure
reason. Sending a reminder never completes the follow-up. Ownership, cover,
escalation and contact history remain available.

**Cover and absence.** Assign only staff with current patient access. A nurse can
cover another assigned team member. For another clinician to cover clinical work,
the primary clinician opens **Authorize time-limited covering clinician** from the
patient record, selects discharge/referral/review, and records an end time. This
is a separate, append-only clinical assignment. Admins can assign that authorized
clinician to a task but cannot create the clinical permission. Coverage expires
or is withdrawn without deleting the task; the task remains actionable and its
owner can be shown as unavailable. Coverage cannot be delegated again, does not
open general diagnosis/psychotherapy records, and grants no bulk-export right.
If the primary clinician cannot authorize coverage, escalate through the practice's
approved process; do not self-assign clinical access.

**Referrals.** Create an incoming/outgoing internal draft with patient, external
practitioner/service name, referral date, responsible staff, action and due date.
Repeated submission of the same form key does not create another referral.
Track `draft → sent → acknowledged → accepted → appointment arranged → completed`,
with explicit decline/cancellation paths. Incoming referrals may be acknowledged
directly from draft; their acceptance/decline is a clinician decision. Sent is a
record of a manually confirmed status, not portal transmission or completion.
Outgoing sharing requires current, purpose/channel/scope-specific verified consent
for the named receiving service. Record response dates and next/outstanding
administrative actions. Link a same-patient scheduled appointment or record an
external arrangement date. Cancellation is surfaced for attention; link a new
scheduled appointment explicitly when rescheduling. Completion needs clinician
confirmation, an actual date at/after the arranged appointment and closure reason.
Private clinical referral records are separate from scheduling fields. No
attachments, referral documents, messages, invitations or external accounts are
created or transmitted.

**Consent.** Use **Consent & contact preferences**, not an unanswered field or an
account/booking as evidence. Append a granted/declined/withdrawn decision for one
of reminders, administrative contact, referral sharing or patient-facing plan
sharing, together with channel, scope, destination, verification, collection
method, notice/version, recorder and date. `practice` scopes routine channels;
referral sharing uses the exact service name; `*` withdraws an entire purpose on
that channel. Each decision retains the prior history. Portal destinations bind
to the linked patient account; phone/email/SMS entered by patients remain
unverified until staff record verification. Optional contact windows use the
chosen IANA timezone. New preview creation and queued-preview rechecks enforce
current decisions; out-of-window delivery is disallowed, not treated as task
completion.

The legacy channel-preference screen remains a compatibility projection, not a
purpose-specific grant. Its “no” choice withdraws reminder/administrative contact
only; it cannot silently withdraw or grant referral/plan sharing. Existing
explicit in-app reminder opt-ins remain valid until superseded, including a
verified guest opt-in still bound to its original booking. They do not become
referral/plan-sharing consent. Withdrawal cancels affected pending/failed unsent
legacy outbox records, leaves sent records intact, preserves history and records
neutral suppression reasons. The verified existing outbox is in-app reminders
only. The new code never inserts external delivery jobs or reactivates cancelled
records. PostgreSQL guards also prevent older consumers from restoring delivery
eligibility after withdrawal and reject sending outside a recorded window.
Consumer transaction/retry behavior still needs staging verification.

Optional communication consent is **not** treated as the legal basis for all
healthcare processing. Drafting care plans/referrals, recording discharge and
recording contact activity already performed are not automatically prohibited by
an optional communication decline. Practice/legal policy must define lawful
processing, exceptions, actual notice texts, verification methods and permitted
contact activity. Nothing automatically expands access to relatives or caregivers.

**Care-plan reviews.** Plan authoring creates one pending review for the version's
agreed date. Earlier pending versions are superseded explicitly when a new plan is
agreed; completed sign-offs remain immutable. The queue shows missing owner/date,
due-soon under approved policy, overdue and unavailable-owner flags. The clinician
records actual review date, private outcome, reviewer and next agreed date; one
new pending review is created transactionally. Merely opening a plan does not
complete it. Historical plan versions are read-only in the review workflow.
Patients need both explicit publication and purpose-specific plan-sharing consent;
shared goals/actions are projected separately from private notes. The latest
signed-off next review date is shown without rewriting the earlier plan version.

**My actions.** Filter by type, owner (`me`, `unassigned` or user ID), due range,
status and selected institution. Switching institutions still uses the existing
authorized institution switch. Missing dates/owners are explicit; a row may have
several attention reasons. Each summary card preserves the other filters and
links to exactly matching source rows. Nurses see only explicitly owned/covered
actions. Clinical covering assignments expand only their named workflow. Exports
are POST/CSRF-protected operational metadata, require existing export authority
and contain no clinical notes/referral text. Invalid/non-positive patient export
filters are rejected. Assistants no longer receive admission totals or directory
badges, and future open stays are not counted as current admissions.

### Exact proposed PostgreSQL forward deployment — not executed live

1. **Preflight on an authorized staging restore:** confirm schema `ramosolo`,
   ledger exactly `[1,2,3,4,5,6]`, matching base key types and the observed legacy
   in-app outbox/preferences contracts. Confirm the next versions remain unused
   immediately before approval. The application deployment configuration must
   explicitly use `DB_SCHEMA=ramosolo`; the historical `lesonto` default is not
   the current target. Use the existing protected credential workflow, never
   pasted credentials or a QA environment file. The live schema was checked through protected
   metadata queries only; no credential or patient/payment record was read.
2. Apply `migrations/007_ramosolo_care_foundation.sql` in staging. It bridges the
   nine missing care/permission foundation tables directly into the existing
   private schema and appends version 7. It does not replay legacy 002/003 or
   replace booking, financial, communication-preference or provenance tables.
3. Apply `migrations/008_ramosolo_care_coordination.sql` in staging. It adds nine
   coordination/history/coverage tables; episode/plan identity indexes and
   matching foreign keys; optional owner/cover/deadline/escalation columns on the
   existing scheduling follow-up; sandbox-preview purpose/suppression metadata;
   and consent/outbox guard functions/triggers. It appends version 8. New tables,
   sequences and guard functions are not granted to public/browser roles.
4. Both scripts use explicit private search paths, a transaction and shared
   advisory lock. Unexpected ledgers abort; lock/statement timeouts are 5 seconds
   and 5 minutes. Index creation may scan/lock parent tables; measure this on a
   representative staging restore and approve a migration window. No existing
   clinical/financial or dataset-manifest row is rewritten. Old preview history
   is preserved and marked ineligible where consent provenance is missing.
5. **Verification before any live approval:** compare schema/constraint/index
   inventory and migration hashes; confirm base appointment, invoice/payment and
   dataset sentinels unchanged; run role/query/export and race tests; exercise
   pending versus sent suppression and attempted requeue; verify consumers use
   an atomic delivery transaction and handle retry/guard errors; verify UTC/SAST,
   contact windows, filters/cards, backup restoration and browser accessibility.
   Reconcile the checkout's missing live booking/financial consumer source before
   deploying an application build; schema-compatible DDL alone is insufficient.
6. **Rollback:** an execution error rolls back that script; if 008 fails after 007
   succeeds, stop and investigate with version 7 retained, rather than replaying
   old versions. After a successful migration, roll back the application to the
   prior approved release while retaining additive tables and all histories.
   Prove that the prior release tolerates ledger version 8 during staging; if it pins
   version 6, prepare an owner-reviewed application revert that understands version
   8 rather than erasing the ledger. Keep withdrawal guards and cancelled-message
   states; never restore consent or
   reactivate messages as a rollback shortcut. Any schema removal requires a
   separately reviewed forward migration after backing up new records. Do not
   delete ledger versions, care histories or provenance to simulate rollback.

No live SQL migration, permission change, deployment, referral transmission,
message or payment is authorized/executed by this implementation. PostgreSQL
verification uses isolated local clusters, synthetic sentinels and loopback only.
The current checkout does not contain the live invoice/payment models or full
legacy scheduler/consumer source; preserving their table data is tested, while
live financial/transport behavior remains unverified. Existing local booking and
clinical regression coverage is retained. This is not a claim of clinical,
regulatory or production readiness.

### Checks and remaining decisions

Run `python -m pytest -q` with dotenv disabled and an explicit test database.
PostgreSQL verification uses local PostgreSQL 18 binaries and no remote URL;
missing binaries cause explicit skips. See `VERIFICATION.md` for actual results,
known unmet broader diagnosis/admission-history cases and browser limitations.

The practice must approve deadline/interval and due-soon windows, absence/on-call
and escalation authority, consent purposes/scopes, collection/verification methods,
notice versions, healthcare-processing bases/exceptions, patient-facing language,
referral acceptance/completion definitions, history retention and reporting privacy.
No questionnaire, diagnosis automation, probability score, medication recommendation
or automatic treatment change is introduced.

# Assistant operational calendar

See [the assistant calendar workflow and migration guide](docs/assistant-calendar.md).
The calendar uses approved server-side availability, versioned change proposals,
explicit administrative-block delegation and synthetic delivery only. Existing
local SQLite installations can use `flask --app app upgrade-calendar` after the
documented coordination upgrades. No live migration is authorized or applied.
The proposed PostgreSQL upgrade is 009 after separately reviewed 007/008;
[migration impact and SHA-256](verification/calendar-migration-impact.json) are
recorded for review. Reconcile this checkout with the richer live scheduling
implementation before any release.

# Browser-exposure security hardening

See [the focused security review](docs/security-review.md) for confirmed findings,
local fixes, synthetic-canary tests, read-only Supabase metadata and outstanding
deployment checks. Only reviewed public assets in `security.PUBLIC_ASSETS` are
served. Existing logins without the new clock fields require sign-in again;
sessions expire after 30 minutes idle or two hours total.

Production now requires `APP_ENV=production`, explicit `APP_TRUSTED_HOSTS`,
secure PostgreSQL TLS and a reviewed HTTPS proxy boundary. The production factory
is `wsgi:create_production_app`; use Waitress on a private/loopback listener.
`APP_TRUSTED_PROXY_HOPS` defaults to `0`; use `1` only for one controlled TLS edge
that cannot be bypassed. Keep credentials server-side. No live grants or RLS were
changed. The [runtime-role check](supabase/review/security_runtime_readonly.sql)
is SELECT-only and must use the protected deployed application connection.

# Public and portal presentation

The medical site now shares a navy/white navbar, footer and role-aware workspace
navigation. Mobile menus work without JavaScript; focus, reduced motion and
keyboard table scrolling are supported. Existing route authorization and CSRF
remain. See [the shell implementation and source-status guide](docs/public-shell.md).

The pasted navbar/footer references are adapted to current routes. The chat
reference is deliberately not connected. The two card images are now transcribed on the professional-information draft.
The supplied base/CSS are still needed for exact reference matching; unconfirmed
phone/address/registration details are withheld. Practice and HPCSA numbers are
separate pending facts. Nothing is independently verified or published live.

For disposable browser QA, run `node verification/check_shell_browser.mjs` with
installed Chrome and Node 24. It creates an in-memory synthetic preview, blocks
external page requests, uses a temporary browser profile and stops its processes.
Results are recorded in [the browser manifest](verification/shell-browser-results.json).
The source/image confirmation status and remaining visual limits are documented
in the guide. No new browser-testing package or frontend build was added.

# Draft privacy and professional information

Latest [local acceptance review](verification/acceptance-review.md) records the
calendar, security, role/navigation, branding and privacy checks actually run.
The separate [live release proposal](docs/local-release-proposal.md) contains
exact candidate migration hashes/order, release gates, verification and rollback;
it does not authorize or claim a deployment.

Local read-only pages are available at `/privacy-notice`, `/data-management` and
`/professional-information`, linked from the shared footer and `/governance`.
Version **0.1-draft** has **no effective date** and no approved privacy contact.
These are unpublished drafts, not a compliance or registration certification.

The card's name, qualification, services and general contact/address text are
source-attributed; practice/HPCSA number digits are withheld until confirmed.
The card email is not automatically designated as an Information Officer contact.
Booking contact agreement remains narrow and does not opt into marketing or
referral sharing. Existing notice acknowledgements are not rewritten.

Complete [the separate owner checklist](docs/privacy-owner-checklist.md) before
publication. [Evidence and unknowns](verification/policy-evidence.json) distinguish
observed application controls from unconfirmed hosting/retention/backup facts.
Fresh infrastructure verification was unavailable at protected token refresh.
The [official-link report](verification/policy-official-links.json) records six
successful Regulator URLs and three unverified HPCSA connections. Recheck with
`python verification/check_official_policy_links.py`; this sends public GETs only,
without credentials, records, cookies or regulatory submissions.

## Booking/login configuration fix

See [database entry-point diagnostics](docs/database-entry-points.md).
`DATABASE_URL` takes precedence over `SUPABASE_DB_URL`; the PostgreSQL schema
default is now `ramosolo`. The connection checker is read-only and does not apply
migrations or initialize missing objects.
