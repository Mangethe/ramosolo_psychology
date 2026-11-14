# Le Sonto / Ramosolo

- Limit this work to the medical portal. Education is an institution placeholder.
- Keep Flask, server-rendered Jinja templates, local CSS and no frontend build step.
- Never read, log, commit or package `.env`, database files, real credentials or real patient data.
- Scope every medical query and mutation through the current institution and role.
- Patient accounts see only their appointments; staff assignments determine access.
- Every modifying form must use CSRF protection. GET must not change operational state.
- Use synthetic data in tests and demos. Do not claim legal, clinical or production readiness.
- Run `python -m pytest -q` after changes to permissions or business logic.
- No automatic institution joins, self-assigned roles or unauthenticated portal signup.
