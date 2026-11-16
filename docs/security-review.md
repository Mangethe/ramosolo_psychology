# Focused Flask browser-exposure security review

Current acceptance rerun: see `verification/acceptance-review.md`. Its real
headless Chrome checks supersede the historical browser-host limitation below
for the listed local surfaces; production edge checks remain unverified.

Local review, 16 November 2026. No live grants, RLS, migrations, credentials or
deployment settings were changed. No real patient records, database files or
secret files were read. Synthetic canaries were used in requests and disposable
files. This is a focused review, not a production-readiness certification.

## Confirmed findings and local fixes

| Finding | Fix and evidence |
|---|---|
| Flask's normal static handler serves arbitrary files beneath `static`, including hidden files | Reproduced against an isolated vanilla Flask instance with a fake `.env`. `SecureFlask` now serves only the explicit release inventory in `security.PUBLIC_ASSETS` (currently `css/style.css`). Traversal, dotfiles, Python, SQL, backups, handoff files, logs, uploads, JSON, unreviewed CSS and source maps are rejected. Symlink escapes are rejected. The real static inventory contained only the public stylesheet; no real credential disclosure was established. |
| Production TLS validation accepted any URL containing `sslmode=`, including `disable` | SQLAlchemy URL parsing now requires `require`, `verify-ca` or `verify-full`. Invalid URLs produce a generic configuration error without echoing the URL. `verify-full` with the correct CA is preferred for deployment; `require` encrypts without providing equivalent server-identity verification. |
| Debug/exception propagation, host trust and proxy/TLS boundaries lacked explicit production enforcement | Production rejects debug settings and `FLASK_DEBUG`, requires trusted hosts, disables exception propagation, and rejects HTTP. Only an explicitly configured single TLS proxy can supply forwarded scheme; forwarded host/client identity headers are not trusted. Added a Waitress production factory. Invalid-host errors use a minimal response without reflecting the host or trying to build URLs. |
| Session lifetime relied on refreshable cookies; legacy remember-cookie restoration could bypass the new clock boundary | Successful password login records nonclinical start/last-seen timestamps. Idle timeout is 30 minutes; absolute lifetime is two hours. Missing, malformed, future or expired clocks fail closed. User loading also validates these clocks, blocking legacy remember-cookie restoration. Existing unstamped logins must sign in again. Password-reset session versions and membership checks remain effective. |
| Cache protection depended on selected URL prefixes | All dynamic/form/error/download responses and authenticated static responses now use `Cache-Control: no-store`, `Pragma: no-cache`, `Expires: 0`, and `Vary: Cookie`. Only successful anonymous public-asset responses may use asset caching. Public forms with CSRF are never shared-cacheable. |
| Framework exception logging could copy sensitive exception values/source lines into logs | Unhandled application diagnostics now log only exception type and the fixed route endpoint. Generic HTTP errors do not render exception descriptions, SQL, stack traces or configuration. SQL parameter hiding remains enabled. Edge/WSGI/database logs require separate deployment review. |
| Login redirects copied an arbitrary original URL/query into `next` | Unauthorized requests redirect directly to `/auth/login` without reflecting query contents. No open redirect or preservation of clinical message text is introduced. |
| Oversized login inputs were truncated | They are now rejected through the generic login failure flow. Existing account lockout and dummy-password-hash behavior remain. |

Additional defenses: removed the Flask `config` object from template globals;
kept Jinja autoescaping; blocked cross-origin unsafe requests in addition to CSRF;
retained frame denial and nosniff; strengthened CSP with explicit object/frame/
connect restrictions; disabled unused browser device/payment capabilities;
applied an origin-only referrer policy globally (see the subsequent shell/browser correction in `VERIFICATION.md`). No CORS access grants are emitted. HSTS is sent for
production HTTPS responses, without assuming subdomain/preload readiness.

## Reviewed data and route boundaries

Reviewed authentication, institution switching, account management, patients,
appointments/calendar, admissions, continuity, clinical records, patient-facing
plans, consent, referrals, reviews, action queues, charts and exports. Queries
derive authorization from active server-side membership and patient assignments/
explicit resource grants. Posted `role`, `institution_id`, `doctor_id`, or another
patient's IDs do not change the acting user's authority. Existing direct-ID,
cross-patient, cross-institution, export and role regressions remain in the full
suite. The security tests add anonymous/patient/assistant/nurse/doctor/admin
crafted requests and response-body canaries.

No oversized record JSON, client-side authorization/filtering, localStorage,
sessionStorage, analytics events, inline script/style blocks, configuration dump
route, user-selected filesystem download route or directory listing was found
in the current medical application. Current CSS remains a separate public asset;
there is no frontend build or JavaScript bundle. Patient/source records rendered
in HTML are selected server-side; export bodies are scoped server-side and built
in memory with fixed attachment names. New JavaScript/CSS must be reviewed and
added to the explicit asset inventory. Do not add source maps automatically.

The browser can always inspect authorized HTML, normal public frontend assets
and its legitimate CSRF tokens. The protection is to never send unauthorized
records or server secrets. No right-click/F12 blocking, obfuscation, encrypted
frontend payload scheme or removal of CSRF was added.

Signed Flask cookies remain client-readable, so they contain only authentication
IDs/version, institution selection, clock values, CSRF state and generic UI
messages. A synthetic clinical submission was verified in the database while
absent from the decoded cookie, redirect URL and captured application logs.
Clinical form fields remain POST bodies. No credentials were fetched or printed;
credential files/history were deliberately not inspected, so this is not a claim
that a repository-history secret scan or credential-rotation audit was completed.

## Actual Supabase metadata review — read-only

Catalog inspection through the existing protected connector found:

- 30 `ramosolo` tables, all owned by `postgres`; none currently has RLS enabled
  and no `ramosolo` RLS policies were present.
- `anon`, `authenticated`, `service_role` and `authenticator` lack `ramosolo`
  schema USAGE/CREATE and data privileges on its tables. No API-role access to
  private sequences or private function execution was found. Disabled RLS alone
  therefore does **not** demonstrate browser API exposure under these grants.
- `postgres` owns all 30 tables and has BYPASSRLS, CREATEROLE and CREATEDB. It is
  not marked superuser. A server using that role has broad private-data authority.
- No dedicated application/runtime role was found. Active connection role names
  do not prove which connection is Flask. The deployed Flask runtime identity is
  **unverified**; no credential file was read to infer it.
- Database role settings did not reveal `pgrst.db_schemas`. The actual Supabase
  control-plane list of exposed API schemas remains **unverified**.
- `public.rls_auto_enable` has SECURITY DEFINER and API-role EXECUTE, but returns
  `event_trigger` and has `search_path=pg_catalog`. It was not invoked or retrieved
  as source. This metadata is not evidence of an ordinary callable data RPC.

The sanitized snapshot is `verification/security-supabase-metadata.json`.
`supabase/review/security_runtime_readonly.sql` contains SELECT-only checks to run
through the protected **deployed runtime connection**, without publishing its URL
or credentials. Running it as the management connector cannot attest Flask's role.

## Proposed live work — not applied

1. Confirm the exposed API-schema list through authorized Supabase settings;
   keep the private medical schema out of browser API exposure and retain the
   current browser-role denials. Review default table/sequence/function grants
   before future migrations. Do not enable broad authenticated SELECT policies.
2. Identify the deployed application role using the SELECT-only runtime report.
   Design a dedicated nonowner, NOSUPERUSER, NOBYPASSRLS, NOCREATEROLE,
   NOCREATEDB runtime identity, with only required object/sequence permissions.
   Keep migration/owner credentials separate from runtime. Provision/rotate its
   credential through the existing protected process, never a browser bundle.
3. Rehearse least-privilege grants and institution/patient RLS in an isolated
   restored environment with all roles and workflows. This requires a reviewed
   design for trusted per-transaction identity/institution context and clinical
   resource grants. **Do not blindly enable RLS or swap runtime roles**: proposed
   foundation migrations already enable RLS without granting browser access, and
   a new nonowner runtime would otherwise lose required functionality. Connection
   pooling must not retain another request's identity context.
4. Submit exact grants/RLS migrations, impact, rollback and verification for
   separate approval. No grant/revoke/role/RLS DDL was executed for this review.

## Deployment checks still outstanding

- Reconcile the current checkout with the richer live schema/booking application
  and the unapplied earlier forward migrations before release. No new database
  migration is required for these Flask hardening changes.
- Set `APP_ENV=production`, an existing protected random signing key, an explicit
  `APP_TRUSTED_HOSTS` list and secure PostgreSQL TLS configuration. Keep passwords,
  database URLs, PATs, signing keys and privileged Supabase credentials exclusively
  in protected server-side configuration; never share them for a test/report.
- Use the production entry point, for example:
  `waitress-serve --listen=127.0.0.1:8000 --call wsgi:create_production_app`.
  Terminate valid HTTPS at the controlled edge. The edge must redirect HTTP before
  accepting sensitive bodies. The app itself rejects HTTP rather than redirecting
  submitted credentials. Never publish Flask's development server/debugger.
- `APP_TRUSTED_PROXY_HOPS=0` is the default. Set it to `1` only for exactly one
  controlled TLS terminator that overwrites forwarded scheme and cannot be
  bypassed. Restrict the backend listener/firewall; test spoofed forwarding headers
  against the real topology. This network boundary was not tested live.
- Do not use the repository as a web document root or static-site upload. Do not
  expose `.env`, `.git`, Python, SQL/dumps, backups, handoffs, docs, verification
  artifacts, logs, database directories, `node_modules`, private uploads or source
  maps through reverse-proxy aliases/object storage. Disable directory listing.
  Serve the reviewed assets through Flask, or reproduce its exact inventory at
  the edge. The Flask guard cannot protect a separate public file server.
- Keep private uploads outside any public directory; any future download endpoint
  must authenticate and check institution/patient/resource ownership before reading
  a fixed storage object. Do not accept filesystem paths from clients.
- Verify CDN/proxy caches honor no-store and never cache authenticated HTML,
  redirects, errors or exports. Keep public-asset caching separate. Purge any
  historical sensitive cached objects using the hosting provider's protected tools.
- Review proxy, WSGI, database and error-monitoring logs. Do not record bodies,
  full URLs/query strings, cookies, authorization headers or opaque guest links;
  use fixed endpoint names and minimal IDs where an authorized audit requires them.
  Confirm log access/retention, TLS/certificates, dependency advisories, edge login/
  unknown-account rate limiting, secret rotation/history and production backups.
- Browser automation was attempted but returned **browser access host unavailable**.
  DevTools Inspect/View Source/Network/storage and desktop/mobile interaction remain
  **unverified in an actual browser**. Flask test-client bodies, headers, cookies,
  direct URLs and static downloads were checked with synthetic canaries. Repeat
  these checks in a synthetic staging browser and at the real edge before release.

## Executed validation

`tests/test_security.py`: **26 passed in 47.49 seconds**, after fixing the initial
invalid-host error response and isolating test request-context caches. Includes
anonymous and all five application roles, crafted ownership/role requests,
static/source probes, symlinks, XSS escaping, generic exceptions/log redaction,
decoded cookies, clinical POST privacy, expiry, legacy remember/tampered cookies,
TLS/host/proxy/debug settings, normal CSRF and cross-origin rejection.

The full regression run passed **201 tests**, with **3 existing expected failures**
and **6 warnings**, in **598.21 seconds**. No failures or skips. This includes the
26 focused cases and the native local PostgreSQL permission, migration and
concurrency checks. `git diff --check` also passed. Full commands and warnings are
recorded in `VERIFICATION.md`. No protections were
removed to make tests pass; the shared synthetic login helpers now supply the same
nonclinical clock fields created by a real successful login.
