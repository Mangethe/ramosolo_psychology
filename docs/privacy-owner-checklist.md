# Privacy and professional-information owner checklist

Status: **unapproved; no officer appointed, registration submitted or live change made**.
Updated 28 November 2026. Proposed version 0.2-draft has **no effective date**.
All owners below are roles to assign, not invented appointments or named officers.
Use the [practice approval decision sheet](privacy-approval-decision-sheet.md) to record the outstanding decisions.

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
| External services and diagnostics | Technical and practice owners | Confirm enablement of optional Gmail, Twilio and identity-provider integrations. Verify host/CDN and operator settings, with request and response capture disabled for login, booking and the clinical portal. |
| Fees, deposits, cancellations and refunds | Practice owner | Approve the service-specific amount, currency, deposit and full cancellation, missed-appointment and refund terms. Confirm how staff disclose them before acceptance outside the enquiry form. |
| Marketing | Practice owner and authorised privacy reviewer | Marketing is disabled. Approve the actual lawful basis, channel and consent evidence before any implementation. Approve the information supplied with each message and the unsubscribe process. |
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
  15-minute idle/two-hour absolute login defaults, CSRF, role checks, no-store responses,
  strict-origin referrers and production TLS requirements. Production edge/keys/
  certificate/backup encryption are not established by code configuration.
- The templates use system fonts and local CSS and JavaScript. Gmail and Twilio adapters
  exist behind enablement controls. See the service inventory below for data flows.
- Earlier read-only Supabase catalog reviews establish the database service. Current
  production region, support access, and the deployed database identity require separate checks.
- GitHub Actions runs tests; it does not establish production hosting location.
  Local SQLite/PostgreSQL synthetic tests do not demonstrate backup restoration.
- No credentials, `.env`, database files or patient records were read. No deletion,
  live migration/grant/RLS change, document submission, officer registration,
  notification or live infrastructure action occurred.

## Findings and local fixes

- **Child and representative access.** A booking stores the enquirer and their contact agreement. It cannot create an account, link a family member or give record access. The form now tells someone enquiring on another person's behalf to use their own details. The dormant [representative authority draft](../supabase/review/representative_authority_draft.sql) links a distinct representative account to the patient and institution, with separate appointment logistics, child-information processing and treatment-consent purposes. The draft records who entered the decision, its policy version, a protected opaque evidence reference and expiry, and retains withdrawal history. It grants no web, worker or Data API permissions. Flask continues to authorise patient access through personal linkage. No date of birth, identity document or family-access form was added.
- **Communication withdrawal.** Previously, deleting email from the selected channels could leave an old verified purpose grant available if email was later selected again. Removing email now records separate withdrawals for reminders and administrative contact. The delivery worker rechecks current preferences and the original decision before sending a queued email. Necessary account/security messages use an independent purpose. An email already handed to the provider cannot be recalled.
- **Marketing.** Transactional mail now explicitly accepts only named security or appointment purposes. SMS adapters support phone verification and security alerts. If the practice later approves marketing, it will need a separate, unticked, channel-specific opt-in with version, purpose, wording, time and actor evidence where consent is the approved basis. Each message must identify the sender and offer an accessible unsubscribe. A separate queue must recheck the latest status at send time and suppress pending marketing on withdrawal without updating the security or appointment preferences.
- **Fees.** The public form sends an enquiry. There is no checkout, card capture or recurring billing. The retained invoice/payment-entry tables in the wider database represent accounting history. Publishing per-category ZAR terms requires `PUBLIC_INSTITUTION_ID`, `BOOKING_TERMS_JSON` and the matching `BOOKING_TERMS_APPROVED_SHA256` from the signed change record. Each entry requires `currency`, `fee`, `deposit`, `cancellation`, `no_show` and `refund`. Amounts are two-decimal strings. With unapproved or unlisted terms the page prompts enquirers to get the terms before they confirm. The form saves no payment acceptance or recurring authorisation. If a separate flow is discovered, verify how it discloses the full amount and timing and records acceptance.
- **Diagnostics.** The app logs error types and registered endpoint names. The security regression injects synthetic values in a path, query, authorization header, cookie and form and checks the response and logs. Deployment review must cover proxy/access logs, database statement logs, edge/WAF sampling, APM and any externally injected browser scripts. Keep useful status, timing and endpoint-template diagnostics. Disable replay, screenshots, heatmaps, keystroke/form capture, request/response sampling, raw URLs and header/body capture on sensitive routes, including error responses. App headers restrict resource loading and disable DNS prefetch. The app cannot control provider or edge collection outside its process.

## External-service inventory

| Service or resource | Where contacted | Information that may leave Ramosolo |
|---|---|---|
| System fonts, local CSS, local session-warning JS | All public and protected views use local assets. Authenticated views use a same-origin session-status request. | Asset and session requests go to the Ramosolo host. Session status contains deadlines and a page identifier. Font files are provided by the device. |
| General questions chatbot | Public home and inpatient pages load a same-site script for predefined answers. | Choices never leave the page and use no cookies, browser storage or free-text input. |
| Analytics, session replay, heatmaps, ad pixels, remote error reporting, CDN assets, external chat, maps and video | No integrations in the reviewed page assets. | No observed external resource requests. Check edge injection, installed monitoring and browser extensions separately. |
| Information Regulator, government and HPCSA | User-selected links from the footer and practice information pages. These are ordinary links with referrer suppression. | Destination and visitor connection metadata when a link is followed. No patient identifiers are appended. |
| Supabase PostgreSQL | Server-side queries from portal workflows, including public booking submissions. | Database-bound account, clinical, booking, consent and audit records as needed by each query. Deployed region, backup locations and support access need confirmation. |
| Gmail API and OAuth token endpoint, or Gmail SMTP over TLS | Server-side delivery worker if enabled. Login, verification, account changes and optional appointment events queue messages. | Sender `clickfoundation.gp@gmail.com`, recipient, delivery metadata and message content. Account verification messages carry a short-lived link. Appointment details require a separate scoped decision. The sending mailbox is distinct from an approved privacy or recovery contact. |
| Twilio Verify and Messaging | Server-side calls from the optional authenticated phone-security workflow. | Destination phone number, verification check data, delivery references and generic phone-change alert content. |
| Configured OpenID Connect provider | User-initiated sign-in or account linking when enabled. The browser follows the authorisation redirect and the server fetches provider metadata, keys and tokens. | Provider sign-in context, client/redirect identifiers, short-lived protocol values, provider subject and token claims. Clinical records are outside the exchange. |
| Payment or recurring-billing provider | No gateway or subscription client in reviewed routes. | No application payment network requests. Billing arrangements outside this checkout need confirmation. |

## Local changes and verification

| Area | Files and checks |
|---|---|
| Enquiry and terms | `booking_terms.py`, `config.py`, `.env.example`, the public controller and `templates/book.html`. Synthetic tests checked per-category amounts, missing/invalid configuration, escaping and enquiry-only wording. |
| Communication and diagnostics | `appointment_email.py`, `security_email.py`, the preferences controller/template and `security.py`. Tests checked purpose allowlisting, queued-message suppression after withdrawal and reselection, continued security notices, and exclusion of synthetic password, OTP, cookie, authorization, path and clinical canaries from errors and logs. |
| Representative authority | `supabase/review/representative_authority_draft.sql`. Synthetic PostgreSQL rejected a foreign-institution patient and a clinical-record scope. Direct database reads failed for API and service roles. A representative decision did not grant clinical access through Flask. |
| Public information | `policy_info.py`, `templates/privacy_notice.html` and `templates/data_management.html`. Draft status, unknowns and official resource links were checked. |

`python -m pytest -q` finished with 314 passed, one skipped and three existing expected failures. Chromium saw zero external page requests in the tested public and authenticated flows. Mobile booking and contact-preference controls passed keyboard checks. Optional external sign-in and live transport configuration were outside the browser run. All message checks used fake transports. The working-tree secret scan and `git diff --check` passed.

The staged-approval update verified that missing approval and mismatched institution or terms keep prices hidden. The test run after this booking change finished with 282 passed and three existing expected failures. Migration-executing and demo-seed modules were excluded. The prior PostgreSQL and Chromium results above remain the baseline. The draft SQL bytes and SHA-256 were verified without applying the draft. New preservation assertions await a separately authorised synthetic rehearsal.

## Release approach

Keep the pages visibly labelled **unpublished drafts**, effective date unset and
privacy contact pending. Complete the evidence/approval checklist, recheck official
resources, then issue a versioned approved notice with the actual responsible
party/contact and effective date. Review offline/operator practices alongside the
website. Do not retroactively label earlier bookings as agreement to this notice.
Follow the existing protected deployment workflow separately. The display and wording changes require no schema change. The representative draft is for review after migration 017 and stays inactive until the practice defines the verified identity and authority process, permitted data, child confidentiality, expiry/revocation, disputed claims and access logging. Review database-role grants and RLS separately before any future activation.

## Official source checks

- POPIA sections 10–14 and 18–24 inform collection minimisation, retention, notice, safeguards and rights procedures. Sections 26–35 cover special and children's information; confirm which grounds and exceptions apply to each workflow. Review cross-border disclosures and operator arrangements under sections 19–22 and 72. [POPIA](https://www.gov.za/documents/protection-personal-information-act) [Information Regulator guidance](https://inforegulator.org.za/guidance-notes/)
- Children's treatment consent and authority require an individual review under the Children's Act alongside applicable confidentiality obligations. Section 129 distinguishes age, maturity, capacity, authority and type of treatment. A representative's authority for one decision gives no blanket permission to disclose records. [Children’s Act](https://www.gov.za/st/documents/childrens-act) [National Health Act, sections 7 and 14–16](https://www.gov.za/documents/acts/national-health-act-61-2003-23-jul-2004)
- Review any proposed unsolicited electronic marketing under POPIA section 69 and the amended regulations. The Regulator publishes guidance on the applicable conditions and Form 4 for the consent route. [Regulator guidance](https://inforegulator.org.za/guidance-notes/) [Amended regulations](https://inforegulator.org.za/wp-content/uploads/2025/04/POPIA-2021-Regulations-FINAL-21-Jan-2025.pdf) [POPIA forms](https://inforegulator.org.za/popia-forms/)
- Review the applicability of the Consumer Protection Act’s advance-reservation and fixed-term rules, and electronic supplier disclosure under ECTA, before introducing financial commitments. [Consumer Protection Act, sections 14 and 17](https://www.gov.za/documents/consumer-protection-act) [Electronic Communications and Transactions Act, section 43](https://www.gov.za/sites/default/files/gcis_document/201409/a25-02.pdf)

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
