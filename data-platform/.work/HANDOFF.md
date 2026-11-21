# HANDOFF: data-platform builder, unattended session 2026-11-21

## Done
- Rename checkins_28d -> checkins_30d in 0006 plus every reference (code, tests, contract drafts). Migration 0007 (prompt 016) moves home_line to a true 30-day window on a new user_route_daily CAGG; tests added (tie-break, window, override). DECISIONS D16.
- Contracts published to contracts/db/ and contracts/api/data-platform.yaml (#27 closed); handoff issues sent to game-engine, insights-sponsors, client-bryan, client-isabella.
- Shared: .attribution-allow plus test (check-attribution passes); issue to game-engine for the rank-4 badge.
- DB-free tests: 63 passed, 53 skipped. Root node tests: 51 pass.

## Blocked (needs Eren)
- DATABASE_URL in ../.env has no password (psycopg: "no password supplied"). So steps 1, 3, 4 (connect, migrate, seed, verify, Tiger Data measurements, docs/TIGER_DATA_RESULTS.md) did not run. #25 commented. MBTA_API_KEY missing, so ingestion (step 5) skipped. Not yet verified on a DB: migrations 0000-0007.

## How to resume
Fix the password in ../.env (sslmode=require is already set), then re-run the builder: connect, migrate, seed, `python -m data_platform.verify`, `python -m data_platform.bench`, write docs/TIGER_DATA_RESULTS.md. Then close #1, #4, #6, #22, #8 with scripts/done.mjs. Prompt 015 (Dockerfile) still queued.
