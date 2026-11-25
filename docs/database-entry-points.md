# Booking and portal database diagnostics

The application accepts `DATABASE_URL` or `SUPABASE_DB_URL` from the server
environment or the existing project `.env`. A nonempty `DATABASE_URL` wins if
both are present. Empty primary values do not hide the Supabase alternative.
PostgreSQL URLs are normalized to the psycopg driver. The default private schema
is `ramosolo`; explicit `DB_SCHEMA` values retain compatibility with other schemas.
The local SQLite filename is unchanged, so existing local data is not moved.

The previously ignored `SUPABASE_DB_URL` could select an empty SQLite database:
opening `/book` then queried a missing `institutions` table, and submitting portal
credentials queried a missing `users` table. The old `lesonto` PostgreSQL schema
default could also select the wrong search path after the intentional rename.

The public booking form now opens without an institution lookup. Submitting it
still requires a correctly configured database and medical institution. A database
outage or schema error returns a generic HTTP 503 with `Retry-After`, not a traceback
or a false successful booking. Authentication failures due to a database outage
are distinguished from invalid credentials without exposing SQL or secrets.

From the application directory, in the same protected environment used to run it:

```powershell
python -m flask --app app:create_app check-connections --only database
```

This command checks metadata only: the selected schema and ORM tables/columns.
It neither reads patient records nor initializes, seeds or migrates anything.
It explicitly labels SQLite as local, not as a working Supabase connection.
PostgreSQL checks use a read-only transaction and bounded statement/connection timeouts.
If missing objects are reported, reconcile the current additive migration plan;
do not replay baseline migrations, drop tables or use `init-db` on hosted data.

`seed_demo_private.ps1` requires the hosted `seed-demo` and `verify-demo`
commands. This checkout registers an empty-database SQLite seeder only. The
hosted prototype in `demo_seed.py` depends on older models and still expects
schema version 6. A schema upgrade alone cannot make the hosted launcher work.
For the hosted schema migration, follow the
[live reconciliation runbook](live-schema-reconciliation-runbook.md).

The protected launcher temporarily sets environment variables and restores them
at exit. Configure the web server process with its own server-side URL and
`DB_SCHEMA=ramosolo`. Keep `.env`, URLs and passwords out of logs and chat.

Regression tests cover the Supabase URL alias, schema selection, no-database form
rendering, safe database failures and recovery-safe login behavior. Live Supabase
access and the user's actual login credentials were not available for this fix.
No hosted schema, accounts, credentials or permissions were changed.
