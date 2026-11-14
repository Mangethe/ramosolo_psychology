# Ramosolo implementation verification

## Observed automated results

`python -m pytest -q`: **43 passed** on Python 3.12, using an isolated SQLite
in-memory database with foreign keys enabled. The test suite covers:

- All five dashboards and admin page rendering.
- Unauthenticated rejection, direct URL restrictions, object-level patient ownership.
- Different institutions, different doctors, nurses and assistant supervision.
- Education membership isolation; membership suspension and password-session invalidation.
- Patient-only appointments; no directory or administrative access.
- Exact 90-day boundary, latest distinct completed visits, future completed data exclusion,
  never-seen, no-show/cancelled exclusions and open admission counts.
- Doctor slot collision, cancelled slot reuse and unique open admissions.
- Admission/discharge permissions; preventing future visits being marked completed.
- CSRF-protected login and POST-only logout, temporary account lockout.
- Booking validation and consent, no intake of unsolicited clinical notes.
- Admin account creation/linking without claiming an existing cross-institution account.
- Private no-store responses and security headers; production configuration fails closed.

A smoke run also rendered public home, sign-in, booking, privacy, inpatient pages
and the doctor workspace without errors. Exact pinned runtime requirements were
installed successfully.

## Not established by these checks

- Live Supabase database connectivity, PostgreSQL migration execution or original data import.
- Real practitioner content, privacy/regulatory suitability, clinical effectiveness.
- Full manual screen-reader, keyboard, mobile and assistive-technology testing.
- External notifications (not implemented), school/education workflows (not implemented).
- Production load, backup recovery, institutional account management procedures.

Only synthetic demo/test data was used. No credentials or database files are
included in the delivered archive.

Browser visual verification was attempted but the environment blocked access to
the local preview. Responsive CSS is implemented but has not been visually
confirmed in a browser during this task. Route rendering is tested separately.
