# Booking/login fix bundle — local application review

17 November 2026. Read `booking-login-fix/README.md`, the entire patch, current
configuration, public booking route, application error/session handling, CLI,
security boundaries and synthetic fixtures before applying the patch.

`git apply --check booking-login-fix/booking-login-fix.patch` exited 0. The
reviewed six-file patch was applied with `git apply`, without force, checkout,
reset, replacement-file copying or migration. All six resulting files matched
the supplied replacements after normalizing line endings. Patch SHA-256:
`33b8b7102ba7575e3b764fd07eb459451fa4e53a288e603cb17c0de8c2d7e2e0`.

The initial tracked working tree was clean; the extracted bundle was untracked.
Later local changes to `.gitignore` and `.gitingnore` were observed and left
untouched. The extracted bundle was not moved, removed or edited. No commit,
remote action, live service restart, seed, migration or deployment was performed.

## Applied behavior

- Nonempty `DATABASE_URL` wins; otherwise `SUPABASE_DB_URL` is accepted before
  the unchanged local SQLite fallback. PostgreSQL schema defaults to `ramosolo`;
  historical schemas remain explicitly configurable. Connections have a timeout.
- Anonymous GET booking rendering no longer resolves an institution. Booking
  submission still requires the database and existing validation/CSRF controls.
  Authenticated requests may still load account/membership data.
- Database failures produce a generic no-store 503 with Retry-After and a warning
  that submission must not be assumed saved. Logs omit SQL/parameters/exception
  messages; error rendering avoids recursively loading the unavailable database.
- `check-connections --only database` inspects model tables/columns and the active
  PostgreSQL schema, using a read-only PostgreSQL transaction. It does not create
  missing objects, modify accounts or migrate data.

Additional integration work: corrected the README's obsolete default-schema
instruction and linked the diagnostic guide. Added `pytest.ini` with
`testpaths = tests` because recursive discovery otherwise collected the duplicate
reference test in the extracted bundle. All tracked application test modules are
under `tests`; no application test was excluded to obtain a pass. Browser-result
metadata was refreshed by the isolated synthetic harness.

## Executed commands and results

All Python runs disabled dotenv loading, set `APP_ENV=test`, selected
`DATABASE_URL=sqlite://`, and used synthetic signing keys. No actual protected
connection URL or account password was read or tested.

```powershell
$env:PYTHON_DOTENV_DISABLED='1'; $env:APP_ENV='test'; $env:DATABASE_URL='sqlite://'; $env:FLASK_SECRET_KEY='synthetic-booking-login-fix'; python -m pytest -q tests/test_database_routes.py
```

**14 passed, 0 failed, 0 skipped in 9.49s**, exit 0. Includes alias precedence,
schema selection, missing tables, safe exception canaries, authenticated database
failure handling, synthetic positive/negative CLI checks and CSRF-protected login.

```powershell
$env:PYTHON_DOTENV_DISABLED='1'; $env:APP_ENV='test'; $env:DATABASE_URL='sqlite://'; $env:FLASK_SECRET_KEY='synthetic-booking-login-fix'; python -m flask --app app:create_app check-connections --only database
```

**Expected exit 1** against the intentionally empty in-memory database: missing
model objects reported, no false success. Positive synthetic initialized-database
CLI verification passes in the 14-test module. This standalone command does not
attest the actual web process's configuration or live Supabase connection.

```powershell
$env:PYTHON_DOTENV_DISABLED='1'; $env:APP_ENV='test'; $env:DATABASE_URL='sqlite://'; $env:FLASK_SECRET_KEY='synthetic-coordination-full-suite'; python -m pytest -q
```

First run: **1 collection error**, caused by duplicate reference tests under the
extracted bundle (not a failed application assertion). After adding `pytest.ini`,
the full application suite was rerun. Completion result recorded below.

**241 passed, 0 failed, 0 skipped, 3 xfailed, 6 warnings in 414.01s (6m54s)**,
exit 0. Includes the 14 new regressions and native isolated PostgreSQL migration,
role and concurrency cases; counts from overlapping runs are not additive.
The expected failures remain the existing structured diagnosis/amendment,
unknown/planned admission and effective-dated care/medical-aid history gaps.
Five warnings concern the deprecated SQLite datetime adapter and one the local
OneDrive pytest cache; no warnings or security protections were suppressed.

```text
node verification/check_shell_browser.mjs
git diff --check -- . ':!node_modules'
```

Browser: **45 checks passed, 0 failed**, exit 0, zero external page requests.
Desktop/mobile, anonymous/all five medical roles, keyboard navigation, real form
login/logout and synthetic response canaries covered. Manifest:
`verification/shell-browser-results.json`; isolated output:
`C:/Temp/ramosolo-shell-juxBdi`. No user browser profile or live database used.
Whitespace check exited 0; only line-ending notices were emitted.

## Limits and next runtime check

No credential file, real patient record or database file was read. No actual
hosting service, live database or user's real login was tested. No database
objects were initialized for the web app. Existing live-schema reconciliation,
privacy/practice approval and release gates still apply.

An authorized operator should run the documented read-only connection check
inside the actual web service's protected environment, and restart that service
using its existing launcher after approval. A seeding launcher's temporary
environment does not configure subsequent web processes. Do not paste its URL,
passwords or `.env`, replay baselines, or run `init-db` against hosted records.
If the checker reports missing objects, review the additive migration plan
separately; this bundle deliberately does not apply it.
