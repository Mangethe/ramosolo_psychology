# Assistant calendar workflow (local implementation)

This extends the Flask/Jinja medical portal. No live migration, deployment,
permission change, payment action, referral transfer or external notification
has been performed. All verification fixtures are synthetic.

## Reused components and scope

The implementation reuses institution membership, supervising-doctor assignments,
`patient_scope`, CSRF, operational auditing, Johannesburg display filters,
administrative continuity archival and the existing notification outbox shape.
Availability maps the current `ramosolo` table names: `availability_policies`,
`availability_sessions`, `availability_exceptions`, `public_holidays` and
`calendar_blocks`. One service (`scheduling_services.available_slots`) handles
staff booking, alternative-time searches and confirmed changes. The public
`/book` page remains an enquiry, never an appointment confirmation.

Doctor assistants use **Appointments → Operational calendar and time proposals**.
They see assigned-doctor appointments for authorized patients only. Doctors have
their assigned patients; administrators have institution-scoped operational
oversight. Nurses have no calendar mutation permission. Patients review only
their own proposals from My appointments. This confers no diagnosis or note
access on assistants or administrators.

Assistants can schedule future visits, explicitly confirm an authorized change,
or propose a change. Completed/no-show attendance records and past scheduled
visits cannot be changed by assistants. Cancel is an explicit, versioned action.
The ordinary status form cannot restore a cancelled booking; use availability
and create a new booking. Clinical attendance recording remains with existing
authorized staff routes.

## Availability and consistency

An enabled doctor/institution policy with a confirmed holiday calendar is
required. There is no permissive fallback. Recurring outpatient sessions remain
Wednesday only; inpatient sessions remain Monday, Tuesday, Wednesday and Friday.
Clinician-approved exception openings can override closures explicitly; the
assistant has no exception/recurring-policy editor. Duration, first-visit and
assessment lengths, breaks, horizon, daily capacity, holidays, leave, blocks and
doctor/patient appointments all affect suggestions. Unexpired existing booking
holds occupy capacity. A legacy appointment without duration metadata reserves
the longest supported visit plus break conservatively, pending staff correction.
Availability output contains times only, without identities or busy-slot reasons.

Change proposals do **not** hold slots or reserve daily capacity. They expire at
the earliest of 24 hours, the original start or proposed start. GET shows effective
expiry without mutating operational state; acceptance, a later proposal or the
explicit Record expiry action records the expired state. Declining or expiry
leaves the original confirmed. Only one pending proposal per appointment is
permitted; a newer proposal supersedes the old proposal with history.

All portal calendar writers lock the scoped doctor's user row in PostgreSQL,
re-read the appointment, and check its `schedule_version`. Acceptance rechecks
the same availability engine inside that transaction. A conditional version
update rejects stale forms. This applies equally to accessible forms and any
future drag-and-drop client; no drag-and-drop implementation was added.
SQLite is for local development; production concurrency relies on PostgreSQL.
Any separate scheduler/import writer must participate in this locking protocol
before release. There is no claim that arbitrary external SQL writers are safe.

Confirmed changes update the existing appointment ID, preserving foreign-key
invoice/payment associations. Calendar history stores actor, action, original
and new times, administrative reason and proposal response history. General
audit logs contain resource IDs and actions, without copied clinical text.

Unsent outbox jobs for old versions are cancelled. The approved reminder policy,
lead times and explicit in-app consent determine replacement jobs. Sent jobs
remain historical. Derived dashboard reminders immediately use the new time.
No reminder silently closes a care follow-up; only obsolete appointment-specific
administrative alerts are archived. Repeating reminder reconciliation does not
duplicate jobs.

## Delegated administrative blocks

The supervising doctor grants/revokes an expiry-dated administrative-block
delegation from the calendar form. This is separate from assistant membership.
An enabled assistant must still be supervised by that doctor. Blocks are future,
administration-only, at most one day long, and cannot overlap an existing visit.
Assistants may release only their own future administrative blocks under an
active delegation. The clinician may release administrative blocks for their
assigned calendar. Existing leave/unavailability/emergency records cannot be
edited through these routes. Block creation/release and delegation changes are
audited; release retains the block record.

## Members, guests and sandbox delivery

Member links use an opaque proposal locator, require the patient's authenticated
active institution membership, and are restricted to that patient's appointment.
Expiry and version checks still apply. No bearer link grants clinical access.

Guests are authorized patient records without a portal user account. An unlinked
public booking enquiry must first be reviewed and represented by an authorized
patient/appointment; this implementation does not silently turn enquiries into
appointments or accounts. Guests need an explicitly granted administrative-email
decision with a verified destination. The opaque 256-bit token is stored only as
a SHA-256 digest; an independently supplied six-digit code is also hashed. The
neutral initial GET reveals no patient or appointment details. POST verification
is limited to five attempts and requires CSRF. The review form shows the proposed
time before a separate accept/decline POST. The exact consent/destination decision
must still be current at response time; withdrawal blocks response.

There is deliberately no real delivery adapter. A local synthetic demo can set
`app.config['CALENDAR_SYNTHETIC_DELIVERIES'] = []` before handling requests and
inspect that in-memory sink in the test harness. It contains synthetic token/code
and destination payloads; never enable it with real records or print/package its
contents. No SMTP, SMS, payment or external notification client is invoked.
Messages are neutral and contain no diagnoses. Token pages use no-store and
origin-only referrer headers. Configure access logs to redact opaque-link paths for any
future external delivery deployment.

## Local setup and proposed live migration

For a new disposable synthetic database, normal `db.create_all()` through the
existing initialization flow includes these models. For an existing **local
SQLite** setup that has already received the documented continuity/coordination
upgrades, run `flask --app app upgrade-calendar`. This adds only missing calendar
columns/tables; it neither enables policies nor sends messages. Do not run this
against patient data. Tests create policies explicitly; no practice schedule is
invented or seeded by this change.

The proposed live file is `migrations/009_assistant_calendar.sql`, after the
separately reviewed **007 then 008** forward migrations. The protected metadata
inspection still found live versions 1–6; nothing was applied. Never replay the
legacy `lesonto` 002/003 scripts on current `ramosolo`.

009 requires exactly versions 1–8 and takes the migration advisory lock with a
five-second table lock timeout. It preserves existing availability tables and
appointment columns with IF NOT EXISTS, adds missing local-compatibility columns,
and creates `calendar_delegations`, `appointment_proposals`, and `calendar_history`.
The three new tables enable RLS and revoke public/anon/authenticated access.
Existing availability configuration, visits, payments, invoices and dataset
provenance are not rewritten. Existing schedule versions are retained. Runtime
access uses the protected server database role and scoped routes, never browser
Supabase table access. Review the exact file and its SHA-256 before approval.

Before live approval: compare current schema/constraints/defaults/indexes and
ledger again, rehearse on an access-controlled restored snapshot without delivery
or payments, inventory all alternate scheduling writers and reconcile the richer
live booking/guest/financial implementation with this checkout. Check existing
appointments with missing duration/session metadata and approve correction
handling. A metadata-compatible synthetic replay is not a full live-schema clone.

Verification after a proposed application: ledger 9; no changed pre-existing
appointment/payment/invoice/provenance values or counts; unchanged availability
rules; new-table privileges; authorized/denied role routes; two concurrent
acceptances; daily capacity; invoice links; consent-aware reminder replacement.
Only then consider exposure. External messaging remains disabled.

Rollback: a failed migration transaction rolls back atomically. After a successful
application, disable calendar entry points and roll back the application release;
retain additive tables, history and columns. Do not drop them or reset accepted
appointments/reminders to old times. Any reverse migration or appointment repair
requires a separately reviewed, backed-up, record-specific plan. Test restoration
before release; no destructive rollback file is proposed.

## Practice decisions and release blockers

Practice review is required for proposal lifetime/no-hold wording, administrative
block delegation duration and release boundaries, approved scheduling policies,
verification/consent collection, guest identity procedures, expiry reconciliation
ownership, and any future external delivery. None is an automated clinical
decision. No availability policy is enabled by this implementation.

Release remains blocked by the checkout/live implementation divergence, the
unapplied 007/008/009 chain, inventory of non-portal scheduling writers, production
identity/delivery integration review. Local desktop/mobile/keyboard Chrome checks
are now recorded in `verification/acceptance-review.md`; physical devices,
other engines and production-edge behavior remain unverified.
This is a local implementation, not a clinical, legal or production-readiness claim.
