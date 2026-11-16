# Assistant calendar verification

For the latest combined acceptance rerun, added guest/history regressions and
actual local Chrome checks, see `acceptance-review.md`. The browser limitation
and counts below describe the earlier calendar implementation phase.

Synthetic local verification only, 16 November 2026. This report distinguishes
executed checks from unverified integration and release work.

The implementation was reviewed against the requested scheduling scope after
the initial inspection. The repository's old hourly-slot booking and
cancel-and-insert rescheduling were replaced with one availability service and
stable-ID changes. Current live schema metadata and check constraints were
inspected through the protected Supabase connector; no patient rows, credentials,
database files or `.env` were read. No live writes were performed.

| Requirement | Evidence |
|---|---|
| Assigned doctor, patient and institution boundaries | Calendar role matrix, denied mutation/availability tests and existing permission suite |
| No clinical permission gained | Existing clinical permission tests remain in the full suite; calendar imports no diagnosis/note models |
| Wednesday outpatient and inpatient weekday rules | Current live check constraints inspected; local model constraints and availability tests |
| Durations, breaks, first visit, capacity, leave, holidays, blocks, existing holds | Synthetic availability regression cases |
| Original preserved until acceptance; no holds | Proposal create/decline/expire/supersede tests; suggested slot remains available |
| Atomic acceptance and stale form handling | Real local PostgreSQL simultaneous accept and overlapping-change/capacity tests |
| Preserve finance associations | PostgreSQL synthetic invoice foreign-key sentinel retains appointment ID and paid amount |
| Reminder replacement | Synthetic current-outbox-shaped SQLite tables: old unsent version cancelled, new in-app job pending, repeated reconciliation deduplicated |
| Explicit block delegation | Grant required; future administrative blocks only; existing visit collision rejected |
| Guest verification and consent | Opaque token, code verification, no details before code, consent withdrawal blocks acceptance, no delivery without verified opt-in |
| CSRF and GET safety | New POST routes reject missing CSRF; GET neither accepts a proposal nor records expiry |
| Migration preservation | Local PostgreSQL legacy/new-schema and synthetic ramosolo forward-chain replay; existing values preserved, ORM columns compared |
| Browser desktop/mobile/keyboard | **Unverified:** browser access host unavailable; native form/template rendering checks are not browser interaction tests |

The first full run passed **167**, with **3 existing expected failures**, in
391.83 seconds (before the final hold and cross-institution cases were added).
An intermediate focused run passed **23** in 41.20 seconds. A separate reminder
replacement test passed **1** in 4.82 seconds. The final full-suite result is
recorded in `VERIFICATION.md`: **174 passed, 3 xfailed, 6 warnings in 406.04 seconds**. The additional native PostgreSQL run passed **20 tests** in 88.66 seconds, including the subsequently added different-start-time interval collision case. These counts overlap; they are not additive.

Actual test infrastructure: SQLite in memory and a native PostgreSQL 18 cluster
created by the test harness on loopback in `C:/Temp`, with synthetic databases
created/dropped there. No remote database test fallback is permitted. The server
is stopped by fixture cleanup; its synthetic logs/data remain outside the repo.
Migration tests use controlled schema replays, not a restored live database.

Mocked/sandbox integrations: invitation delivery is an in-memory synthetic sink;
outbox testing uses synthetic tables shaped from safe schema metadata; finance
association checks use a synthetic FK table. Real email/SMS, reminder workers,
payment processing, external calendar providers and live Supabase migrations were
not exercised. No live messages, document transmissions or payment calls occurred.

The three pre-existing expected failures cover broader structured diagnostic
history, unknown/planned admission representation, and effective-dated financial/
transfer/practitioner histories. They are not passing validations. Financial chart
parity in the richer live application remains unverified by this checkout.

See `docs/assistant-calendar.md` for clinician/policy decisions, setup, the exact
proposed 009 migration, its required predecessors, impact, verification and
non-destructive rollback approach. Live release remains blocked by the checkout/
live implementation divergence and unreconciled alternate scheduling writers.
