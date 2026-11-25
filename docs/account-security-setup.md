# Ramosolo account-security rollout runbook

Flask-Login and Werkzeug password hashes in the portal's `users` table remain the account authority. PostgreSQL stores authentication state and the existing institution and role assignments. Supabase Auth is outside this login flow. A linked OpenID Connect identity can provide the first factor for an existing portal account.

## Rollout decision

**Hold production rollout.** This runbook covers the local review and synthetic rehearsal. Supabase, production data, live delivery, and SSO activation are outside this review. Flask-Login and the existing local password store remain authoritative.

The release owner must confirm the mail adapter, sender and support details, recovery staffing, database role, secret custody, and a restore rehearsal before scheduling the cutover. OIDC can be deferred independently. Do not roll out a new authentication gate before users can receive verification messages and staff have a working recovery route.

## Migration order

| Stage | Review | Additive PostgreSQL draft |
|---|---|---|
| Reconciliation | Current production-shaped catalog and reviewed preflight | `010_ramosolo_live_reconciliation_draft.sql` |
| 1 | `portal_sessions.py`, session routes, both base templates, and `static/js/session-warning.js` | `011_portal_sessions.sql` |
| 2 | `account_verification.py`, the verification routes, provisioning, and `security_email.py` | `012_account_verification_and_mail.sql` |
| 3 | `multi_factor.py`, MFA routes, account security settings, and the new email types | `013_authenticator_mfa.sql` |
| 4 | `sso.py`, the OIDC link and confirmation forms, and provider configuration | `014_federated_identity.sql` |
| 5 | Gmail transports, delivery worker, and purpose-scoped appointment messages | `015_outbound_email.sql` |
| 6 | Managed phone ownership verification and local rate reservations | `016_phone_ownership_verification.sql` |

The observed fixture starts with the `ramosolo` ledger at **1–6**. Rehearse the exact production-shaped fixture followed by **010 → 011 → 012 → 013 → 014**, then apply drafts **015 → 016** on the isolated candidate. Migration 010 records internal ledger versions **7–9**. The later drafts do not change that ledger. Record 011–016 individually in the approved deployment change record. Do not replay 001–009 against the observed schema. Migration 010 retains its separate [reconciliation review, preflight and restore procedure](live-schema-reconciliation-runbook.md).

Each file is its own transaction. Confirm the before/after state before proceeding to the next file. The combined application and worker expect the auth and delivery drafts. No account or patient rows are backfilled. For a disposable SQLite rehearsal, `flask --app app:create_app init-db` creates the current schema.

Before any approved application, confirm the actual server major and schema, current ledger, owners and default privileges, catalog fingerprints, file hashes, and the backup/PITR point. Run the approved comparison during the change window. The PostgreSQL 17 branch of 010 checks the exact constraint fingerprint. PostgreSQL 18 is insufficient to rehearse that guard. Stop on any drift, ownership discrepancy, restore failure, or incomplete prior stage.

Use a named migration owner and a private application runtime role. The auth tables enable RLS and revoke grants from PUBLIC, `anon`, and `authenticated`. Choose and test the actual runtime grants and RLS policies before release. A non-owner runtime needs schema USAGE, only the required table operations and audit sequence access, and an explicit private policy for its server-only role. Keep the mail worker separate where possible. It needs to claim/update account mail jobs and read the verification fields needed to render queued verification messages. Confirm the selected roles with `flask --app app:create_app check-connections` and synthetic read/write tests as those roles. That command checks schema shape and does not establish RLS permissions. The reconstructed fixture uses its approved `postgres` object owner and does not establish that the chosen production runtime role is ready.

## Configuration names

Set values in the runtime environment or secret manager. These examples use synthetic domains and omit secret values.

| Name | Example or default |
|---|---|
| `AUTH_IDLE_SECONDS` | `900` |
| `AUTH_WARNING_SECONDS` | `120` |
| `AUTH_ABSOLUTE_SECONDS` | `7200` |
| `AUTH_PUBLIC_URL` | `https://portal.example.test` for HTTPS, or the synthetic local loopback origin |
| `AUTH_SUPPORT_PHONE` | Approved staffed recovery number. A business-card contact is a development fallback only. |
| `AUTH_VERIFICATION_SECONDS` | `3600` |
| `AUTH_VERIFICATION_KEY` | Dedicated secret-manager value for verification signing. Local development can use the Flask signing key. |
| `AUTH_REQUIRE_STAFF_MFA` | `1`. Startup rejects disabling it outside synthetic tests. |
| `AUTH_MFA_KEY` | Dedicated Fernet key from the secret manager. Generate with `Fernet.generate_key()` in the approved secret-management process. |
| `AUTH_SSO_ENABLED` | `0` |
| `AUTH_OIDC_ISSUER` | `https://identity.example.test` |
| `AUTH_OIDC_CLIENT_ID` | `ramosolo-portal` |
| `AUTH_OIDC_CLIENT_SECRET` | Secret-manager value |
| `AUTH_OIDC_REDIRECT_URI` | `https://portal.example.test/auth/sso/callback` |

Set `APP_TRUSTED_HOSTS` to the exact canonical host. Set `APP_TRUSTED_PROXY_HOPS` to the actual supported proxy topology and block direct access to the backend. Terminate TLS at the approved edge, redirect HTTP before it accepts bodies, and check HTTPS, secure cookies and HSTS. Account links use `AUTH_PUBLIC_URL`. Configure the edge, application access logs and analytics to omit verification and OIDC callback query strings. Confirm support routing and coverage before issuing user instructions.

Store `FLASK_SECRET_KEY`, `AUTH_VERIFICATION_KEY`, `AUTH_MFA_KEY`, database credentials, and future mail and OIDC credentials in the approved secret manager. Assign owners, use separate values per environment, and limit each secret to the processes that need it. Keep signing and encryption values stable across workers and retain an approved recovery path. Changing the Flask key invalidates cookies. Changing the verification key invalidates outstanding links, which must be reissued. Losing the MFA key requires assisted recovery or a reviewed key restore. Keep servers synchronised and rehearse secret restoration and rotation without printing secret values.

## Sessions and inactivity

An authenticated browser receives an opaque identifier. The server stores its hash, account version, membership fingerprint, deadlines, and MFA approval. Logout revokes the server session. Institution changes issue a new identifier while retaining the original absolute expiry. Password, email, MFA, and membership changes invalidate earlier sessions through the account version. If an operator changes membership outside the application, increment the user's session version in the same transaction. Existing pre-upgrade cookies require sign-in.

The status endpoint and browser polling are read-only. While the warning is closed, a visible tab can send one CSRF-protected request per minute after a trusted click or keypress. The warning's **Stay signed in** button sends the same request. Session extension updates idle expiry after successful validation and preserves absolute expiry. Tabs verify status before showing private content and recheck on broadcasts, page restoration and foregrounding. They clear the old page and its unsaved inputs at expiry, confirmed logout, or a session change. A local deadline also clears a page while offline. Protected content starts hidden until the browser can confirm the session with JavaScript.

Warn staff to save early or extend before expiry. The application never copies clinical content or drafts to persistent browser storage. **Sign in again** opens the normal login flow without a patient URL. After verification and applicable MFA, reopen the record to load current authorised data from the server. Only previously saved records are restored. An old tab or old cookie cannot resume the draft. A suspended tab is rechecked when the browser next runs it. The portal cannot retract screenshots, completed downloads, or content separately copied by a user.

Schedule `flask --app app:create_app purge-expired-auth` according to the operator's retention and monitoring plan. Expired sessions are rejected even before that cleanup runs. To force reauthentication across the practice after an incident, revoke the affected users' sessions and pending authentication records using a reviewed operator action.

## Verification and delivery

The practice administrator and owner CLI still provision new accounts. Existing medical accounts establish verification of their current recorded address when they first submit the correct local password after the cutover. This queues confirmation without issuing a portal session. Confirmation is followed by a fresh sign-in and staff authenticator setup. Neither operation assigns a role or changes a membership. Existing medical accounts with invalid or unreachable addresses need the authorised correction process before they can sign in. Review addresses and staff coverage before cutover. Education remains a placeholder.

The user opens the verification link and selects **Confirm email**. The link expires after the configured lifetime. Resend permits one message per minute and up to three in an hour per account, superseding the previous token. The welcome email is queued once when the account is confirmed and has an enabled membership. If the membership is approved later, the provisioning path queues it then.

Account mail uses a separate transactional outbox. The existing reminder outbox serves appointment-linked in-app notices and retains its own consent rules. Queue processing cancels superseded verification jobs and retries temporary failures with backoff, up to five attempts. Logs record a generic failure and attempt count. A real adapter must honor the supplied idempotency key across retries, including after a worker crash between provider acceptance and the database commit.

For review, keep `FakeMailProvider` and synthetic addresses. `flask --app app:create_app deliver-email` uses the fake adapter and runs only against disposable non-production SQLite. It prints the synthetic processing count only. The Gmail adapter and worker require the separate activation controls below.

### Gmail mail pilot

The sender is **clickfoundation.gp@gmail.com** in the MIME header and Gmail authenticated-send target. Mail authorisation is independent of the portal's Google OIDC configuration. Use a separate Google Cloud OAuth client and enable Gmail API. With the mailbox owner's approval, obtain offline OAuth consent for `https://www.googleapis.com/auth/gmail.send` only. Store the refresh credential in the worker's secret manager and verify the mailbox and header in an approved isolated pilot. Gmail manages SPF/DKIM for its own domain. If the practice later changes to a custom sender domain, separately verify SPF, DKIM and DMARC alignment with its domain owner. [Gmail API scopes](https://developers.google.com/workspace/gmail/api/auth/scopes) · [Gmail send API](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send)

| Worker setting | Pilot configuration |
|---|---|
| `MAIL_PROVIDER` | `fake` by default. Choose `gmail-oauth` for approval review. |
| `GMAIL_OAUTH_CLIENT_ID`, `GMAIL_OAUTH_CLIENT_SECRET`, `GMAIL_OAUTH_REFRESH_TOKEN` | Worker-only secret-manager entries for the dedicated Gmail consent. |
| `GMAIL_APP_PASSWORD` | Only for explicit `gmail-smtp-app-password` mode and where Google permits app passwords. Create a dedicated password under two-step verification. Store it in the worker secret manager and revoke it when no longer needed. |
| `MAIL_DISPLAY_NAME`, `MAIL_REPLY_TO` | Set the approved display name. Leave Reply-To empty until a monitored address is approved. |
| `AUTH_PUBLIC_URL` | The canonical HTTPS portal origin. |
| `MAIL_PILOT_RECIPIENTS` | Exact, comma-separated individually approved pilot inboxes. |
| `GMAIL_DAILY_LIMIT` | Required positive reservation cap from 1 to 100 per worker database per rolling day. Begin with a small number. |
| `MAIL_LIVE_ENABLED` | Keep `0`. Set to `1` only for an approved pilot. |
| `APPOINTMENT_EMAIL_ENABLED` | Keep `0` until the practice approves electronic appointment messages and verifies recipient preferences. |
| `APPOINTMENT_EMAIL_REMINDER_MINUTES` | Keep `0` for no email reminder. Set one approved lead from 1 to 10080 minutes when enabling reminders. |

The fallback uses TLS to `smtp.gmail.com:465` and the dedicated app password. Never use the normal mailbox password or lower its two-step protection. Gmail controls availability of app passwords. [Google app-password guidance](https://support.google.com/accounts/answer/185833)

After separate approval, configure a single worker to start, keep its credentials out of the web process where possible, limit egress to the selected transport and run a deliberately bounded `flask --app app:create_app deliver-email --live --limit 5` on the approved PostgreSQL worker. Verify one seed event of each approved message kind with allowlisted inboxes only. Check provider acceptance, then independently confirm inbox delivery in that pilot. Disable by stopping the live worker and setting `MAIL_LIVE_ENABLED=0`. Gmail mailbox limits also cover activity outside this app. Monitor provider quota and rejection rates before widening eligibility. [Gmail sending limits](https://support.google.com/mail/answer/22839)

Account mail covers email verification, welcome, completed login and security-setting changes. Verification, welcome and login messages suppress stale destinations. Security-change alerts may intentionally use the previous address. The public booking request form gives an on-screen receipt. It queues no confirmation email. A scheduled appointment queues confirmation in its own transaction. Reschedules, cancellations and reminders use appointment state, version and independently recorded verified email preferences. The worker rechecks these and the recipient before sending. It suppresses stale events and respects applicable contact windows. Only an explicit verified `appointment_details` scope for the same purpose and destination adds the date and time. Messages carry one recipient and no diagnosis, notes, medical-aid details, service or attachment.

The worker distinguishes pending, sending, simulated, accepted, cancelled, failed and uncertain rows. Acceptance means the provider accepted the message, with inbox delivery still unknown. Old `sent` rows predate that distinction. Gmail offers no application idempotency contract for this send API. The worker deduplicates by event, persists a claim before sending, and never retries an ambiguous provider response or a stale sending claim automatically. Reconcile uncertain rows through the approved mailbox procedure before authorising any manual reissue. Known retryable failures back off for up to five attempts. Quota responses pause the mailbox worker across processes and respect the configured application reservation cap. Review retention for metadata, terminal outcomes and synthetic fixtures. Failure logs contain no message body, addresses or credentials.

### SMS ownership pilot

SMS is provisioned for phone ownership verification. Existing authenticator MFA, recovery codes and assisted recovery remain independent. A verified number enables neither SMS login nor appointment reminders. Enabling either would require a separate approved purpose and control design. There is no provider callback or webhook in this implementation. Only a synchronous provider verification check for the server-bound challenge can approve ownership.

| Setting | Pilot configuration |
|---|---|
| `SMS_PROVIDER` | `disabled` by default. `fake` is available only in synthetic tests. `twilio-verify` selects the managed adapter. |
| `SMS_POLICY_APPROVED` | Keep `0` until the provider, spending cap, geographic policy, user eligibility and old-number notices are approved. |
| `SMS_ELIGIBLE_ROLES`, `SMS_ALLOWED_REGIONS` | Comma-separated approved medical roles and ISO region codes. Example `patient` and `ZA,GB`. Empty lists do not enable the feature. |
| `SMS_DAILY_MAX` | Explicit app-wide dispatch cap from 1 to 100 per rolling day. Count old-number notices and uncertain attempts too. |
| `SMS_KEY`, `SMS_LIMIT_KEY` | Separate server-side Fernet and HMAC secrets. Keep them stable across workers. Changing the limit key resets address/IP counters. Rotate only after outstanding code windows have elapsed. |
| `SMS_PROVIDER_VALIDITY_SECONDS` | Confirm actual configured provider validity before activation. Twilio's standard period is 600 seconds. The portal challenge lasts at most 300 seconds. |
| `TWILIO_ACCOUNT_SID`, `TWILIO_VERIFY_SERVICE_SID`, `TWILIO_API_KEY`, `TWILIO_API_SECRET` | Dedicated approved Twilio account or subaccount, Verify Service and minimally scoped worker credentials. |
| `TWILIO_SECURITY_MESSAGING_SERVICE_SID` | Dedicated Messaging Service for non-OTP old-number change notices. Required so changes never silently skip the old channel. |

Before enabling, configure Verify Fraud Guard and explicitly approve provider geography settings, a sender and security template, billing thresholds and a spend alert/disable procedure. Do not assume provider alerts enforce a hard cap. The application reserves sends against its own durable daily cap and separate account, destination and observed IP counters. Configure per-client edge throttling behind a trusted reverse proxy. The app deliberately does not trust supplied forwarded IP headers. If the app sees only the proxy address, the local IP limit applies to that aggregate. Check the region allowlist on the Verify Service and the security-notice Messaging Service. [Twilio Verify Fraud Guard](https://www.twilio.com/docs/verify/preventing-toll-fraud/sms-fraud-guard) · [Twilio Verify code validity](https://www.twilio.com/docs/verify/api/rate-limits-and-timeouts) · [Twilio Verify Check](https://www.twilio.com/docs/verify/api/verification-check)

The account holder supplies an international number such as `+27 …`, their current password and a fresh authenticator code. Full numbers are encrypted for the account/contact purpose and masked in the UI. A change requests a generic alert to the old verified phone before sending a new challenge. Failure to accept the alert blocks the change. An unavailable old channel goes through the existing two-administrator recovery process. That process revokes the old verification and records the revocation in the audit log. Direct ownership verification invalidates the old portal session and queues a generic safety email. It leaves MFA and access privileges intact.

Resend keeps the same local challenge and expiry and follows provider code reuse within its validity period. One challenge can make at most three sends with escalating cooldown and five checks. A destination lease extends through the external code-validity window, so another account or session cannot inherit a still-valid code. Ambiguous send/check outcomes fail closed. Verify OTPs are sent directly through the managed service and never enter the email or appointment queue. This release exposes no webhook. If one is added in a future review, verify its signature against the externally visible URL and body before processing, and keep authentication decisions synchronous.

## MFA and recovery

Staff must complete authenticator setup before their first authenticated portal session. Patients can enrol from **Account security**. A valid first code activates the key and displays ten single-use recovery codes once. Authenticator keys are encrypted and recovery codes are hashed. A password-only or pending-MFA browser has no protected route access. Each accepted time step is consumed once across sign-ins. Five bad challenges trigger a five-minute account factor lockout; keep server clocks synchronised because verification uses the current 30-second time step.

A user can sign in with their password and a saved recovery code. Within five minutes of that recovery sign-in they can re-enter their password, select **Replace authenticator**, and verify the new app. Replacing the app invalidates the previous app and unused codes. Other changes to security settings require the current password and a current authenticator code when one is configured. A staff member must keep an authenticator. A patient who chooses to disable it must prove possession of the current authenticator.

If the user loses the app and all codes, open an opaque incident ticket and verify identity through the approved practice channel. Telephone or email possession alone is insufficient. Require two distinct verified, MFA-enrolled medical administrators for that institution who are independent of the target. The second reviewer must approve the evidence and independently confirm any replacement mailbox. Each administrator enters their own password and fresh authenticator code at the controlled operator console. Never collect those credentials in the ticket or share them between reviewers.

```text
flask --app app:create_app start-assisted-recovery --institution-id <id> --user-id <id> --requestor-id <id> --approver-id <id> --ticket <opaque-id>
```

Use `--replacement-email` or `--reset-password` only after separately approving the replacement. Both prompt privately. Deliver any replacement password through the approved identity-proofed channel. The command rejects self-recovery, duplicate tickets, a non-admin approver, cross-institution or multi-institution targets, and invalid factor proof. Successful use records both operator IDs and the ticket, revokes the target's sessions, pending authentication, linked SSO and prior authenticator, invalidates old recovery codes, and requires email confirmation and the applicable MFA enrolment. It adds a distinct audit event for password replacement. The confirmed user then signs in with their local password and completes fresh setup. The tool changes no memberships or patient contact fields. If the account is shared across institutions or the practice has fewer than two eligible independent admins, pause and escalate to the named owner/security reviewer for a separately approved, audited multi-institution or console recovery. Do not create privileges just to satisfy a recovery request. The older unaudited password-reset command is confined to synthetic SQLite tests. Assign backup contacts and rehearse the escalation before cutover.

## OIDC activation

Keep the flag at `0` for cutover and recovery rehearsal. After separately approving the provider and tenant, register a confidential client and exactly one canonical HTTPS callback, `<AUTH_PUBLIC_URL>/auth/sso/callback`. Use the approved tenant issuer, client ID and secret, and check discovery issuer, HTTPS token/authorization/JWKS endpoints, RS256, client-secret authentication and PKCE S256. Test signature, nonce, issuer, audience and replay rejection in the chosen provider's test tenant. Test prompt behaviour because `prompt=login` requests provider reauthentication but portal logout does not end a provider session.

An existing signed-in user links their provider from **Account security** after proving their password and enrolled factor. The callback validates the signed identity token, issuer, client audience, and nonce. The user then explicitly confirms linking. Only the provider's issuer and immutable subject identify the link. Matching email alone grants no access. SSO sign-ins still need the local account to be eligible and the portal's MFA policy to be met. Portal logout revokes the portal session. The provider's own session has its separate lifecycle.

## Activation order and checks

1. **Owners and recovery first.** Assign release approver, migration operator, rollback owner, mail/DNS operator, and two recovery reviewers with backup coverage. Verify restore/PITR and approved identity-proofing and mailbox correction. Rehearse two administrator enrolments, recovery and authority checks in isolation.
2. **Prepare delivery and cutover support.** Confirm the canonical URL and recovery contact. Complete the approved mail adapter and sender authentication rehearsal. Give existing users advance notice. Review any missing or inaccessible mailbox with the account owner through the approved recovery process. Keep live delivery off while reviewing.
3. **Database change window.** After separate authorisation, use the approved owner and verified files. Have staff sign out and close pre-cutover portal tabs. Run the read-only preflight, establish a restore point and hold writes, then complete 010 followed by 011–016 in order. Confirm ledgers, objects, ACL/RLS, schema health and preservation evidence after each stage.
4. **Activate the combined application only when prerequisites pass.** Provide the dedicated keys and correct runtime role, enforce HTTPS and clock synchronisation, and enable only the separately approved mail worker. Leave SSO disabled. Pilot with agreed staff and patient accounts. Confirm first-time verification and MFA, temporary lockout recovery, patient-only access and institution scoping before opening broadly.
5. **Check immediately and monitor.** Confirm copied cookies and stale tabs fail closed, logout and downtime clear screens, fresh MFA restores authorised saved data, and pending accounts cannot reach protected URLs. Check queue ages, retries, provider acceptance and bounces, one welcome, audit records, auth errors and runtime RLS. Suppress sensitive payloads in logs.
6. **Stop or roll back safely.** Pause wider activation, disable SSO if applicable, stop delivery for misrouting, and use a maintenance hold on protected access if an auth guard or migration fails. Preserve evidence and involve the rollback owner. Revoke affected sessions and verify recovery before reopening. Avoid rolling back to a version that would reopen unverified access. Use the verified restore plan if a database rollback is required.
7. **Optional OIDC pilot later.** After local login and recovery are stable, test the actual provider separately and get approval before changing the flag. Confirm local MFA and revocation remain enforced with the provider both on and off.

## Decisions still open

- Approve Gmail transport, mailbox owner consent, display name, staffed Reply-To if any, exact allowlisted pilot recipients, mailbox/queue quota ownership and terminal failure handling. Approve appointment recipient/detail policy separately.
- Confirm the canonical HTTPS portal URL, the practice support contact, and who receives account-recovery escalations.
- Assign who may approve assisted recovery and the evidence and second review required for staff accounts.
- Choose the OIDC provider and tenant, client authentication method, exact redirect registration, discovery endpoints, and the policy for removing or reassigning links.
- Schedule onboarding and communications for existing accounts, approve the mailbox-correction and shared-account recovery pathway, and assign secret storage and rotation ownership.
- Confirm the actual PostgreSQL runtime role's grants and private RLS access, and define migration and rollback ownership.
- Keep SMS disabled until Verify and notice sender approval, supported countries, eligible roles, provider fraud/geo controls, billing alert ownership and daily budget are recorded.

## Test evidence and file identities

The earlier CI-compatible full run moved from **226 passed, 29 skipped, 3 xfailed** to **244 passed, 30 skipped, 3 xfailed**. Eighteen account-security cases added 18 passes. The additional PostgreSQL auth draft case added one skip when the local PostgreSQL fixture was disabled. The earlier **254 passed, 1 skipped, 3 xfailed** in the reconciliation runbook was the 226-case baseline with its 28 PostgreSQL cases enabled. The rollout review added three focused cases for existing staff, the MFA disable guard, and dual-control recovery. The final SQLite full-suite run finished with **247 passed, 30 skipped, 3 xfailed**. These counts are from distinct runs and should not be added.

Rollout rehearsal used Python 3.14 on Windows and loopback-only synthetic PostgreSQL databases. Of the 11 previously unrun PostgreSQL cases, nine passed on 18.0. The constraint-definition drift case initially failed there because 010's exact definition fingerprint guard is restricted to PostgreSQL 17. It passed on the separately checksum-verified **17.11** build, which also passed the end-to-end fixture test, affected auth-draft case, and all seven PostgreSQL role/scope cases. Thus all eleven previously unrun cases passed. This replay matches the observed PostgreSQL patch version and tests a reconstructed fixture rather than the managed service itself.

The end-to-end fixture test compared existing table rows projected onto their original columns, excluding the separately checked ledger. It compared existing table owners, ACLs, and RLS settings before/after 010 and again before/after 011–014. It included a synthetic clinical record before the auth drafts. Existing users, password hashes, memberships, patients, appointments, and the clinical sentinel survived. All new auth tables were empty after migration. The app then completed email onboarding with synthetic credentials and exercised booking, calendar, outbox and institution boundaries without external email delivery.

Headless Chrome passed the privacy checks at desktop (1280 × 800) and mobile (390 × 844) sizes. The test confirmed keyboard focus and desktop extension, expired both views offline, and verified that the saved clinical text and unsaved narrative were gone from the old DOM. Local storage, session storage and IndexedDB were empty. The desktop no-JavaScript view kept the record hidden. After fresh password and MFA, only the saved record reloaded and the form was blank.

### SHA-256 of the exact files exercised

| File | SHA-256 |
|---|---|
| `tests/fixtures/ramosolo_live_fixture.sql` | `3DD805990226224C60DEF3C468DC62EE9F1E098B0D7DB66338369E9C128490DE` |
| `010_ramosolo_live_reconciliation_draft.sql` | `50067E6FE6898C494D153943242E4F277D9A50BC49695D01B51D69860E054A34` |
| `011_portal_sessions.sql` | `6DE3CB9D9E6855C56D0081067C2BF4ADB60B21F6DE22787F3A6B192B7BF5A83A` |
| `012_account_verification_and_mail.sql` | `6294E5520DB19AD6969D4C4049582D9F8817C6629096AD6466564909AF135319` |
| `013_authenticator_mfa.sql` | `A33CEBF113621BD8267974531BB8202287C69B7DE566879E8B2A0E98F70406F9` |
| `014_federated_identity.sql` | `FB913275AAD5DDC0007AA4F6AAD96C03D6BCCF9D057A80E51BC12081108E455E` |
| `015_outbound_email.sql` | `56CC602EE3D3285A8310D3D26E925370D9863457594E509033238A885A5072AF` |
| `016_phone_ownership_verification.sql` | `C3C6EF006DA8CCB7D31B6C2D0C8E8DF05287CAC081E0CF7D8629B691F46C8D76` |

010's hash matches the [separately reviewed hash](live-schema-reconciliation.md). Verify file bytes again on the release checkout.

The PG18 historical compatibility cases also used these source files. The tests adapt some statements in memory for a synthetic schema or a negative control. None of these files belong to the rollout sequence above.

| Historical SQL source | SHA-256 |
|---|---|
| `001_initial_postgres.sql` | `8786EEF10E3E642CE967EF5AAA29A424084B047BD58D94422CA3BDB5B79D34CF` |
| `002_care_continuity.sql` | `43405BC0D192A2EC728BA64181DFF9C55B3245202A19F6A0B0F182A32AF3FD21` |
| `003_explicit_permissions.sql` | `E484D5BC5D4041F582BE52961FD42DC46051DD7D66983EB1DC041981684AF6EA` |
| `007_ramosolo_care_foundation.sql` | `90C33A59D6C7126DD571CC084FFE9A34DC1889627C6A059C38256126616EADBF` |
| `008_ramosolo_care_coordination.sql` | `CCC29E0D1552F5E121C7A948680260D1C29C74D95D823E469A15BA3F9D7CD443` |
| `009_assistant_calendar.sql` | `B7EA5EFBFED3BF4A24F318BD93D25441E123AF2E3AADC0B6CF5CF3CB5196110D` |

### The 30 full-suite skips

One module-level skip is `tests/test_demo_seed.py`. It depends on eleven absent legacy ORM classes and the absent `Med/MedWebsite/reminders.py`. It remains unverified and is unrelated to the synthetic auth and fixture tests.

The following 29 node IDs are in `tests/test_independent_postgres.py`. The full run uses a deliberately unavailable `RAMOSOLO_POSTGRES_BIN` to keep the PostgreSQL fixture off. Each listed test requires an isolated cluster with Windows `initdb.exe`, and the fixture never falls back to a remote database.

| # | Node ID suffix | Separate evidence |
|---:|---|---|
| 1 | `test_factory_cli_schema_after_rollback_and_connection_reuse` | Prior isolated PG18 pass |
| 2 | `test_reconciliation_draft_aborts_atomically_on_incompatible_catalog` | This review, PG18 pass |
| 3 | `test_reconciliation_draft_applies_to_reconstructed_production_fixture` | This review, PG18 pass |
| 4 | `test_constraint_fingerprint_is_order_stable_and_rejects_definition_drift` | This review, PG17.11 pass |
| 5 | `test_reconciliation_draft_rejects_observed_schema_drift_atomically` | This review, PG18 pass |
| 6 | `test_reconciliation_draft_rolls_back_after_midflight_failure` | This review, PG18 pass |
| 7 | `test_reconciliation_draft_rolls_back_when_postcondition_fails` | This review, PG18 pass |
| 8 | `test_reconciliation_migrated_fixture_supports_app_writes_and_boundaries` | This review, full chain on PG17.11 |
| 9 | `test_account_security_drafts_are_additive_and_private` | This review, PG17.11 pass |
| 10 | `test_new_database_migrations_match_orm_and_preserve_synthetic_existing_rows` | This review, PG18 pass |
| 11 | `test_current_schema_name_and_migration_ledger_are_incompatible_without_reconciliation` | This review, PG18 pass |
| 12 | `test_simultaneous_check_ins_deduplicate_and_preserve_both_reports` | Prior isolated PG18 pass |
| 13 | `test_simultaneous_same_doctor_bookings_do_not_double_book` | Prior isolated PG18 pass |
| 14 | `test_simultaneous_proposal_acceptance_is_idempotent_and_preserves_invoice` | Prior isolated PG18 pass |
| 15 | `test_simultaneous_overlapping_changes_respect_daily_capacity` | Prior isolated PG18 pass |
| 16 | `test_simultaneous_different_start_overlaps_are_rechecked` | Prior isolated PG18 pass |
| 17 | `test_simultaneous_acknowledgment_has_one_state_transition` | Prior isolated PG18 pass |
| 18 | `test_postgres_role_and_cross_institution_record_queries[dr]` | This review, PG17.11 pass |
| 19 | `test_postgres_role_and_cross_institution_record_queries[dr2]` | This review, PG17.11 pass |
| 20 | `test_postgres_role_and_cross_institution_record_queries[nurse]` | This review, PG17.11 pass |
| 21 | `test_postgres_role_and_cross_institution_record_queries[dr_assist]` | This review, PG17.11 pass |
| 22 | `test_postgres_role_and_cross_institution_record_queries[admin]` | This review, PG17.11 pass |
| 23 | `test_postgres_role_and_cross_institution_record_queries[patient]` | This review, PG17.11 pass |
| 24 | `test_postgres_role_and_cross_institution_record_queries[foreign]` | This review, PG17.11 pass |
| 25 | `test_diagnosis_join_negative_control_for_synthetic_financial_totals` | This review, PG18 pass |
| 26 | `test_forward_ramosolo_007_008_preserve_financial_provenance_and_guard_outbox` | This review, PG18 pass |
| 27 | `test_simultaneous_referral_creation_and_state_update` | Prior isolated PG18 pass |
| 28 | `test_simultaneous_review_signoff_preserves_one_signed_review_and_next_task` | Prior isolated PG18 pass |
| 29 | `test_simultaneous_discharge_recording_creates_one_episode_followup` | Prior isolated PG18 pass |

### Rehearsal commands

Disable dotenv, set `APP_ENV=test`, set `DATABASE_URL=sqlite://`, and clear `SUPABASE_DB_URL` before running tests. For the full SQLite run set `RAMOSOLO_POSTGRES_BIN` to an unavailable path and run `python -m pytest -q -rs`. For the intended fixture chain and negative control, point `RAMOSOLO_POSTGRES_BIN` at the checksum-verified PG17.11 binary directory and set `RAMOSOLO_POSTGRES_MAJOR=17`.

```powershell
python -m pytest -v -s -p no:cacheprovider tests/test_independent_postgres.py -k 'constraint_fingerprint or migrated_fixture_supports or account_security_drafts or postgres_role' --tb=short
python verification/check_auth_expiry_browser.py --browser 'C:/Program Files/Google/Chrome/Application/chrome.exe'
```

The browser test uses optional Playwright and a local in-memory synthetic database. It launches a loopback app and uses an installed Chromium binary.

### Gmail and SMS delivery extension checks

The full CI-compatible run finished with **262 passed, 32 skipped, 3 xfailed**. The two new PostgreSQL skips were verified separately as described below.

The new synthetic suite is `python -m pytest -q tests/test_delivery.py tests/test_account_security.py`. It exercises mocked Gmail API and SMTP calls, email dispatch outcomes, booking commits and obsolete reminders, and synthetic ownership challenges with quota, race, replay and recovery controls. Live mailbox acceptance, delivery to an inbox, Twilio geo rules, actual spending limits and sender registration are pilot checks still outstanding.

The delivery extension adds two PostgreSQL cases to the historical skip inventory, `test_delivery_drafts_preserve_existing_jobs_and_keep_private_tables` and `test_simultaneous_phone_checks_claim_once_in_postgres`. Both passed separately on an isolated PostgreSQL 18.0 cluster. The first checks that drafts 015 and 016 preserve existing queued rows and keep new tables private. The second races two submissions against a fake SMS provider and confirms that only one calls it.

The complete production-shaped synthetic replay through **010 → 011 → 012 → 013 → 014 → 015 → 016** also passed on PostgreSQL 17.11. It checks preserved pre-existing rows and private delivery-table access. The reviewed bytes of 010–014 still match the hashes recorded before the extension.
