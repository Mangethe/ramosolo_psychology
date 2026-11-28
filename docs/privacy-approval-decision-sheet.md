# Ramosolo privacy approval decision sheet

**Approval status** Pending. Record the approver, approval reference and effective date for each decision in the practice’s change record. All three are unset.

| Decision | Current setting | Practice approval required | Affected feature and configuration location |
|---|---|---|---|
| Guardian authority and confidentiality | Guardian portal access disabled. Permitted representative actions and evidence process unset. The SQL draft records decisions only. | Approve authority verification, capacity and confidentiality assessment, permitted actions and fields, handling of disputed claims, expiry, revocation and access audits. Decide whether to authorise an appointment-logistics pilot. | Patient accounts, appointments and records. `access.py` and `supabase/review/representative_authority_draft.sql`. Future access requires a separate implementation and grant review. |
| Privacy contact and rights requests | Responsible legal party, named handler, secure request channel, effective date and approved procedure unset. Public notice labelled draft. | Name the legal party and accountable handler. Approve the secure intake channel, proportionate identity and authority checks, request register, response and escalation process and applicable timeframes. | `/privacy-notice`, `/data-management`, `policy_info.py` and the practice request procedure. The Gmail sender is configured separately. |
| Email, SMS and optional sign-in | Gmail sender `clickfoundation.gp@gmail.com`. Repository defaults are fake mail, live delivery off, appointment email off, SMS disabled and OIDC off. Actual live enablement, provider regions and approved reply/support routes unset. | Confirm provider contracts, subprocessors and processing/support locations. Approve sender/reply handling, permitted purposes and any pilot. Keep marketing disabled. | `MAIL_PROVIDER`, `MAIL_LIVE_ENABLED`, `MAIL_REPLY_TO`, `APPOINTMENT_EMAIL_ENABLED`, `SMS_PROVIDER`, `SMS_POLICY_APPROVED`, `AUTH_SSO_ENABLED` in protected server configuration. |
| Hosting and diagnostics | Supabase PostgreSQL identified. Web host, edge, database and backup regions, and live diagnostic settings unset. Application diagnostics use error types and registered endpoints. | Identify the host, edge, database, backups and support locations. Approve minimal logging, access and retention. Verify replay and sensitive request or response capture are disabled. | Protected database connection, hosting/edge/monitoring consoles and `security.py`. |
| Fees and booking terms | `ZAR` supported. Actual fees, deposits, cancellation, missed-appointment and refund terms unset for every category. Public booking is enquiry-only. | Approve the values and wording below per applicable category and identify who provides the full terms before booking acceptance. | `/book`, `PUBLIC_INSTITUTION_ID`, `BOOKING_TERMS_JSON`, `BOOKING_TERMS_APPROVED_SHA256` in protected server configuration. |

## Retention periods

Approve a period, start event, owner, legal-hold handling and disposal method for each category. Short-lived authentication expiry is an access control.

| Record category | Current period | Affected feature and configuration location |
|---|---|---|
| Enquiries and appointments | Unset | Booking and calendar records. Practice retention schedule and database maintenance. |
| Clinical records, admissions, care histories and exports | Unset | Portal and approved copies. Practice records schedule and authorised disposal. |
| Consent, withdrawal and representative evidence | Unset | Communication decisions and future authority records. Practice evidence schedule and protected evidence store. |
| Accounts, verification artefacts and authentication logs | Unset | Account history. `purge-expired-auth` can purge selected expired technical records. Production schedule is unset. |
| Email/SMS queues, delivery histories and provider copies | Unset | Application outbox and provider dashboards. Practice schedule, worker and provider settings. |
| Audit logs and operational diagnostics | Unset | Application audit records and web, edge, database and monitoring logs. Practice schedule and operator retention settings. |
| Financial records and payment history | Unset | Billing and accounting records. Practice billing retention schedule. |
| Backups, restore copies and recovery snapshots | Unset | Database, host and backup consoles. Approve expiry, access and treatment of restored withdrawals. |

## ZAR fees and terms

| Enquiry category | Fee | Deposit | Cancellation | Missed appointment | Refund |
|---|---|---|---|---|---|
| Individual therapy | Unset | Unset | Unset | Unset | Unset |
| Children and family support | Unset | Unset | Unset | Unset | Unset |
| Couples therapy | Unset | Unset | Unset | Unset | Unset |
| Assessment enquiry | Unset | Unset | Unset | Unset | Unset |
| Inpatient coordination | Unset | Unset | Unset | Unset | Unset |
| General consultation | Unset | Unset | Unset | Unset | Unset |

[Staged rollout and recovery](local-release-proposal.md#privacy-approval-and-staged-activation) · [Supporting evidence and provider inventory](privacy-owner-checklist.md)
