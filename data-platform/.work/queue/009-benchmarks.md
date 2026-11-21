---
id: 009
title: Demo benchmark - compression ratio and aggregate latency
status: done
depends_on: [005, 006]
---
## Goal
A repeatable benchmark that produces the demo numbers: compression ratio on realtime tables and continuous-aggregate vs raw query latency.

## Context
- `../DECISIONS.md` D12 (demo numbers)
- `src/data_platform/bench.py` stub from 005
- `migrations/0003_realtime.sql`, `0004_aggregates.sql`

## Steps
1. `python -m data_platform.bench [--synthetic-days 7] [--users 2000]`: if real ingested data is thin, generate synthetic vehicles (realistic: ~600 vehicles every 15 s for N days, run in batches with COPY), predictions, rider_events and points_ledger rows, in a separate schema-safe way (tag synthetic rows, e.g. `vehicle_id` prefix `synthetic-`, users with username prefix `bench_`), so they can be deleted with `--cleanup`.
2. Compress eligible chunks (`compress_chunk` on chunks older than 1 day), refresh CAGGs, then measure: table size before/after and ratio per hypertable; median of 20 runs for (a) weekly global leaderboard via `leaderboard()` vs the same sum over raw `points_ledger`, (b) home line via `home_line` vs raw `rider_events`, (c) "vehicles at stop in last 300 s" query.
3. Write results to `bench/RESULTS.md` (table with environment: local docker or Tiger Cloud, row counts, sizes, ratios, latencies, timestamp) and `bench/results.json`.

## Acceptance criteria
- One command produces RESULTS.md with all numbers filled.
- `--cleanup` removes all synthetic rows and users.
- Numbers recorded locally; if `TIGER_DATABASE_URL` is set, run the same against Tiger Cloud and add a second column.

## Tests to run
`pytest -q`; add a small smoke test that runs the bench with tiny sizes (`--synthetic-days 1 --users 10`) and checks the JSON keys.

## Out of scope
Charts or slides.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
