---
id: 016
title: Analytics, recommendations and Boston analytics on Postgres, plus latency numbers
status: ready
issue: 1
depends_on: [014, 015]
---
## Goal
Run `/analytics/me`, `/analytics/boston` and `/recommendations` on Tiger Data in postgres mode by executing our `sql/*.sql` files against data-platform's continuous aggregates. Record aggregate vs raw query latency for the demo (the Tiger Data prize angle). Memory mode stays as it is.

Billing rule: local docker TimescaleDB or the Tiger Cloud Free plan only.

## Context
- `../data-platform/migrations/0006_insights_aggregates.sql` (read only): `user_stop_daily` (bucket, user_id, stop_id, route_id, visits), `user_stop_hourly` (bucket, stop_id, user_id, checkins), view `stop_popularity_hourly` (bucket, stop_id, checkins, unique_users), view `home_line` (user_id, route_id, checkins_28d; counts checkin + ride_start). `0004_aggregates.sql`: `personal_stats_daily`, `user_stop_visits`. `0005_schema_v01.sql`: `place_visits`.
- `../data-platform/.work/reports/012.md` (migration 0006 was not executed there; you may be the first to run it, so report any failure precisely)
- `insights-sponsors/sql/*.sql` (from 006 and 012), `src/insights_sponsors/analytics.py`, `recommend.py`, `repo/postgres.py` (from 014), `scripts/load_seed.py`
- `src/insights_sponsors/consent.py`: the place-affinity query runs only after `has_consent(..., "place_visits")`

## Steps
1. `src/insights_sponsors/sqlfiles.py`: load `sql/*.sql` and split them into named queries (`-- name: <q>`), cached. Unknown name raises KeyError.
2. Align the SQL files with the real names in 0006 (`home_line.checkins_28d`, `stop_popularity_hourly.unique_users`, `user_stop_daily.visits`, `stops.id` not `stop_id`, `stores.id`, uuid `user_id`). Keep the parameter names. Update `tests/test_sql_files.py` if names change.
3. Add `analytics_me(user_uuid, period)`, `boston_analytics(period)` and `recommendation_inputs(user_uuid)` (or equivalent) to `PostgresRepository`, executing the named queries. Keep the k-anonymity rule (`min_users = 3`) in SQL. Refactor `analytics.py` and `recommend.py` so the scoring and response assembly is shared and only the data fetching differs per backend. Do not duplicate the ranking logic.
4. Remove the `NotImplementedError` stubs from 014 for these paths.
5. `scripts/load_seed.py --demo-events` (off by default; prints "DEV ONLY"): insert our `rider_events.json` and `place_visits.json` for the dev usernames (mapping `days_ago`/`hour` to timestamps), plus a `place_visits` consent row for users whose seed visits exist. Then refresh the aggregates with `CALL refresh_continuous_aggregate('<name>', NULL, NULL)` for `user_stop_daily`, `user_stop_hourly`, `home_line_weekly` and `personal_stats_daily`. Refuse to run with `--demo-events` unless the host is `localhost`/`127.0.0.1` or `--i-know-this-is-shared` is passed.
6. `scripts/bench_queries.py`: with a DATABASE_URL, run each named query 30 times (after 3 warm-ups) and print p50/p95 ms. For `busiest stops` and `home line`, also run a raw-table equivalent over `rider_events` and print the speedup. Optional `--events N` generates N synthetic rider events for 50 fake dev users first (only on localhost, with the same guard as step 5) so the numbers mean something. Write the results to `insights-sponsors/docs/bench.md` (table, date, row counts, machine note).
7. Tests (`@pytest.mark.db`, skipped without `DATABASE_URL`): after `load_seed.py --demo-events`, `/analytics/me` for `user-1` in postgres mode matches memory mode on `unique_stops`, `home_line` and `top_stops[0]`; `/analytics/boston` hides buckets below 3 users; `/recommendations` reads no `place_visits` without consent (revoke, then assert no `stop` items from affinity); and the conformance shape checks pass in postgres mode. Always-on tests (no DB): `sqlfiles.py` parsing and that every named query referenced in code exists.
8. If a local DB is available, run everything plus the benchmark and paste the `docs/bench.md` table into the report. If not, say so plainly. Do not create cloud resources.

## Acceptance criteria
- `python -m pytest -q` passes without a DB.
- With a local DB: `python -m pytest -q -m db` passes and `docs/bench.md` exists with real numbers.
- Postgres and memory modes agree on the hand-checked user-1 numbers.
- The consent gate on place visits holds in postgres mode (tested).

## Tests to run
- `cd insights-sponsors && python -m pytest -q`
- With `DATABASE_URL` (local): `python scripts/load_seed.py --demo-events && python -m pytest -q -m db && python scripts/bench_queries.py --events 200000`

## Out of scope
- Schema changes (if one is needed, mark this `blocked` and name the exact column or view). Writing to `../contracts/` or data-platform files.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
