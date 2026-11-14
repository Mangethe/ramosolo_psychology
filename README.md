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

| Capability | Doctor | Nurse | Doctor assistant | Patient | Admin |
| --- | --- | --- | --- | --- | --- |
| Dashboard | Assigned cohort | Assigned care cohort | Supervisor's cohort | Own appointments | Current institution |
| Patient/contact records | Assigned | Explicitly assigned | Supervisor's patients | No patient directory | Institution-wide |
| Schedule/cancel appointments | Assigned patients | Read only | Supervisor's patients | Read own only | Institution-wide |
| Mark completed / no-show | Yes | No | No | No | Yes |
| Admit/discharge | Assigned | Assigned | Read only | No | Institution-wide |
| Accounts, requests, activity log | No | No | No | No | Current institution |

An admin sees all records **in their selected medical institution**, not every
institution in the database. There is no global superadmin web account.
Institution creation and verified cross-institution membership are owner CLI
operations. Suspending a membership removes that institution's access without
suspending the user's unrelated memberships. A disabled doctor supervisor also
removes the assistant's patient scope. Nurses must be explicitly assigned from a
patient record by its doctor or institution admin.

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

No diagnoses, therapy notes, prescriptions, billing, chat, document uploads or
unrequested clinical modules were introduced.

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
4. `DB_SCHEMA` defaults to `lesonto` and must match the applied migration. Use a
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
cli.py                        Local seed and owner provisioning
Med/MedWebsite/controllers/    Public and medical routes
Med/MedWebsite/templates/      Medical views
Edu/                          Explicit education placeholder
models/                       Core, RBAC, medical, education placeholder, governance
templates/                    Shared, auth, users, institutions, admin, public views
static/css/                   Local stylesheet, no frontend dependencies
migrations/                   PostgreSQL new-database baseline
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
