# Privacy and professional-information owner checklist

Status: **unapproved; no officer appointed, registration submitted or live change made**.
Prepared 16 November 2026. Proposed draft version 0.1-draft has **no effective date**.
All owners below are roles to assign, not invented appointments or named officers.

## Decisions required before live publication/use

| Decision | Owner to assign | Evidence needed / current limitation |
|---|---|---|
| Responsible legal practice/entity and relationship to Ramosolo / Le Sonto Medical | Practice owner / authorised legal reviewer | Card gives practitioner name, not the complete legal responsible-party identity |
| Approved privacy contact, Information Officer/deputy identity and registration where applicable | Practice owner | No appointment, registration evidence or approved privacy mailbox supplied; general card email must not be silently designated |
| Version, effective date, approval/sign-off and review process | Practice owner | Draft date is not an effective date; approve and retain each policy version |
| Grounds/purposes for each information category and any special-information processing | Authorised privacy/legal reviewer with clinician | Do not treat optional reminder consent as authority for all healthcare processing; address booking/contact agreement independently |
| Access/correction/objection/deletion procedure and identity/representative verification | Privacy handler to appoint | Approved minimal verification method, secure channel, authorised handlers, request register, applicable deadlines/fees/exceptions and complaints process; no automatic ID upload/email verification is implemented |
| Children, guardians, adolescents, caregivers and family information | Responsible clinician with privacy/legal reviewer | Competence/authority/consent/access/third-party redaction policy, disputed authority handling and record of verification; no automatic caregiver login/access |
| Current recipients and external sources | Practice owner / clinical and operations leads | Actual facilities/referrers/insurers/care partners, offline/paper/billing records, purpose and authority for disclosures; do not imply integrations exist |
| Hosting/operators, contracts, subprocessors and processing locations | Technical operator and practice owner | Web hosting, database region, support access, backups, email/SMS, monitoring/CDN and cross-border evidence; a South African address or Supabase project is not proof of processing location |
| Record-class retention and legal holds | Clinician / privacy/legal reviewer | Current applicable professional and statutory requirements, rationale and authorised disposal; do not adopt an arbitrary number of years from an example |
| Backup and recovery plan | Technical operator | Schedule, locations, encryption/key access, retention, recovery objectives, successful restore evidence and reapplication of restrictions after restore |
| Secure disposal | Technical operator / records owner | Database, exports, devices, paper and backup disposal procedures/evidence; cancellation/expiry is not deletion |
| Audit/logging governance | Privacy owner and technical operator | Audit access/retention, clinical history versus general logs, proxy/database/monitoring minimisation and no tokens/clinical text in request logs |
| Incident handling and notification | Practice owner to designate responsible handler | Incident contacts, reporting/triage/containment/evidence process and review of applicable notification duties/current Regulator eServices process; no invented 24/48/72-hour promise |
| Actual contact/monitoring hours | Practice operations / responsible clinician | Card has no hours. Confirm privacy/telephone/request hours separately from individual patient plan monitoring; no continuous-monitoring claim |
| External notifications/calendar/payments/AI/analytics | Technical and practice owners | Currently no live external delivery/payment/AI client in this checkout; verify wider production system before approving negative or positive claims |
| Notice/booking acknowledgement provenance | Practice owner and implementation reviewer | Current booking stores its contact-agreement timestamp, not the text/version of a privacy notice. Decide whether an additive version-capture change is required before approval; do not rewrite old acknowledgements or imply they accepted this new draft |
| Official links and accessibility | Publication owner | Regulator pages reviewed; HPCSA live availability/redirects must be rechecked where retrieval failed; mobile/screen-reader review and accessible request alternatives |

## Card transcription and confirmation

Both images supplied by the user were inspected read-only. The professional page
attributes the following to the card rather than independent verification:

- Ponky Ramosolo; Clinical Psychologist; M.A. Clinical Psychology.
- Address as printed: 10th Floor, Room 1033, Louis Pasteur Hospital,
  374 Frances Baard Street, Cnr Sisulu. Confirm the street spelling, postal city
  and current location rather than silently substituting the old placeholder.
- Cell 081 854 0795; telephone 012 320 6942; fax 086 234 6878;
  email clinicalpsychologistP@gmail.com. Check every digit against the original
  and confirm current operational use before live publication. These are not an
  approved Information Officer/rights-request channel. They are non-clickable
  reference text on the local professional draft, not an invitation to send records.
- The reverse lists individual therapy for adults/adolescents, couples therapy,
  play therapy for children, parent psychotherapy, intellectual/cognitive/emotional
  assessment for children/adolescents, the listed presenting concerns, and HIV/AIDS.
  Confirm scope/current availability. Do not silently remap stored booking service
  codes or claim the card guarantees suitability/outcomes.
- A number is printed with **Prac. No.**, not as an HPCSA registration. No practice
  or professional-registration digits are included in public constants/pages.
  Obtain a practice-confirmed HPCSA identifier, profession/category and current
  status, and separate permission to publish it. No registry lookup was performed
  and no official endorsement is claimed.

## Evidence reviewed, not assumed

- Booking controller/model: required name/email/phone/category/preferred time and
  limited contact agreement; request is not a booking/account or clinical record.
- `access.py`, controllers, permissions and exports: institution/assignment scopes,
  explicit clinical grants, patient-facing projections and metadata audit events.
- CommunicationDecision / coordination services: separate purposes/channels,
  history, verified destinations and unsent-notice suppression on withdrawal.
- CarePlan/check-in view: actual individual monitoring hours; no general hours.
- Scheduling/continuity services: internal workflows, in-app outbox compatibility,
  in-memory synthetic guest delivery and sandbox previews; no external referral send.
- Authentication/security config: hashed passwords, signed nonclinical cookies,
  30-minute idle/two-hour absolute login, CSRF, role checks, no-store responses,
  strict-origin referrers and production TLS requirements. Production edge/keys/
  certificate/backup encryption are not established by code configuration.
- No analytics, chat or external fonts/scripts in reviewed templates. No live
  email/SMS/payment provider is configured by this change. Wider infrastructure
  and provider-side logging cannot be inferred from this checkout.
- Existing sanitized Supabase schema/security metadata from earlier read-only
  review exists. Fresh protected project/provider lookup failed at OAuth token
  refresh; do not infer a provider region, current RLS/grants or Flask runtime role.
- GitHub Actions runs tests; it does not establish production hosting location.
  Local SQLite/PostgreSQL synthetic tests do not demonstrate backup restoration.
- No credentials, `.env`, database files or patient records were read. No deletion,
  live migration/grant/RLS change, document submission, officer registration,
  notification or live infrastructure action occurred.

## Release approach

Keep the pages visibly labelled **unpublished drafts**, effective date unset and
privacy contact pending. Complete the evidence/approval checklist, recheck official
resources, then issue a versioned approved notice with the actual responsible
party/contact and effective date. Review offline/operator practices alongside the
website. Do not retroactively label earlier bookings as agreement to this notice.
Follow the existing protected deployment/migration workflow separately. No new
database migration is needed for these local draft pages.

## Official source checks

The [Information Regulator complaints page](https://inforegulator.org.za/complaints/),
[POPIA forms](https://inforegulator.org.za/popia-forms/),
[access-to-record guidance](https://inforegulator.org.za/paia/),
[eServices catalogue](https://eservices.inforegulator.org.za/services.aspx) and
[security-compromise guidance](https://inforegulator.org.za/2025/08/19/fact-sheet-handling-of-security-compromises/)
were reviewed as official sources. Those pages and the Regulator homepage returned
HTTP 200 in the explicit public-link check. The current complaints resource points
to eServices; do not substitute an old email-only submission promise.

[HPCSA](https://www.hpcsa.co.za/),
[iRegister](https://www.hpcsa.co.za/iregister/) and
[professional complaints](https://hpcsa.co.za/Public/Complaints) were identified on
the official domain in search results. Direct web retrieval and HTTPS probes could
not be completed. Reachability is **unverified**, not a successful registration
lookup. Recheck before approval; do not disable TLS verification to obtain a pass.
See `verification/policy-official-links.json` for status/redirect metadata and
`verification/policy-evidence.json` for evidence/unknowns. No third-party registry
proxy, practitioner query or regulatory submission was used.
