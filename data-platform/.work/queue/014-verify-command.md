---
id: 014
title: One-command verification run for when a database exists
status: ready
depends_on: [013]
---
## Goal
Make the human run that closes every DB-unverified item a single command: `python -m data_platform.verify`. It must be safe to run against local docker or Tiger Cloud, and it writes a report the planner can review.

## Context
- `README.md` (Quickstart, Load MBTA data, Benchmark sections)
- `src/data_platform/migrate.py`, `seed.py`, `load_static.py`, `ingest.py`, `bench.py`
- Issue #25 (human needs DB + free MBTA key)
- Billing rule in `../AGENTS.md`: nothing here may use Anthropic keys or any pay-per-usage service

## Steps
1. `src/data_platform/verify.py` (`python -m data_platform.verify [--skip-mbta] [--skip-bench] [--bench-days 2]`), steps in order, each timed and recorded as pass/fail/skipped with the error text:
   a. connect to `DATABASE_URL` and print server version and `timescaledb` extension version (hostname is never printed or written);
   b. `migrate()`, then `migrate()` again and assert nothing applied (idempotency);
   c. `seed`;
   d. if `MBTA_API_KEY` is set and not `--skip-mbta`: `load_static`, then one `ingest` cycle; record row counts for routes, stops, route_stops, vehicles, predictions, alerts; otherwise mark skipped;
   e. run `pytest -q` as a subprocess and capture the summary line and any failures;
   f. unless `--skip-bench`: `bench` with small defaults (`--synthetic-days 2`), then `--cleanup`;
   g. list hypertables, compression settings, jobs and continuous aggregates from `timescaledb_information`.
2. Write `verify/VERIFY.md` (human-readable) and `verify/verify.json`, with a timestamp and environment label (`local` or `tiger_cloud`, detected from `sslmode=require` in the URL). Exit non-zero if any step failed. Continue after a failed step so the report is complete.
3. README: a "Verify everything" section with the exact commands for local docker and for Tiger Cloud.
4. Unit test the report rendering and step bookkeeping with fakes (no DB): a failing step still produces a full report and a non-zero exit code.

## Acceptance criteria
- `python -m data_platform.verify` without a DB writes a report that says the connect step failed, and exits non-zero (no stack-trace crash).
- Unit tests pass without a DB.
- No secrets or hostnames in the report.

## Tests to run
`pytest -q`; also run `python -m data_platform.verify --skip-bench` once with no DB and include the generated VERIFY.md text in the report.

## Out of scope
Installing Docker, Postgres or Tiger CLI (human step, #25).

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
