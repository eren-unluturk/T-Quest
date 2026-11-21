---
id: 012
title: City-wide Boston analytics endpoint (GET /analytics/boston)
status: done
issue: 3
depends_on: [011]
---
## Goal
The brief lists "Boston analytics" next to personal route analytics, and it is the most visual Tiger Data showcase (time_bucket over many riders). Add an anonymous, aggregate-only city view: busiest stops, trending neighborhoods, and line activity over time. No per-user data is exposed.

## Context
- `insights-sponsors/openapi/insights-sponsors.yaml` (version 0.1.1 after 011; this prompt makes it 0.2.0)
- `src/insights_sponsors/analytics.py`, `repo/base.py`, `repo/memory.py` (`rider_events`, `stop_popularity`, `stops`, `route_stops` from 006)
- `insights-sponsors/sql/*.sql` (header and parameter conventions from 006)
- `../data-platform/migrations/0004_aggregates.sql` (read only: `personal_stats_daily`, `leaderboard_daily`) and the promised `stop_popularity_hourly` (#22)

## Steps
1. OpenAPI: add `GET /analytics/boston` (bearer auth) with query `period` enum[week, month] (default week) returning `BostonAnalytics` {period, generated_at, total_checkins, active_riders, busiest_stops: [{stop_id, stop_name, checkins}] (top 10), trending_neighborhoods: [{neighborhood, checkins, change_pct}] (the current period vs the previous period of equal length, top 5 by change_pct, only neighborhoods with 5 or more check-ins in the current period), lines: [{route_id, checkins, by_day: [{day, checkins}]}]}. Bump `info.version` to `0.2.0` and add an `x-changelog` entry.
2. Privacy rule (put it in the endpoint description too): suppress any bucket with fewer than 3 distinct riders (k-anonymity). Leave out a busiest_stop or neighborhood entry backed by fewer than 3 distinct users, and report `active_riders` as 0 when it is below 3.
3. `sql/analytics_boston.sql`: named queries (`-- name: ...`) using `time_bucket('1 day', ...)` over `stop_popularity_hourly` (busiest stops, neighborhoods via `stops.neighborhood`) and `rider_events` (lines by day), with `%(since)s`, `%(prev_since)s` and `%(min_users)s` parameters and the k-anonymity filter as `HAVING count(DISTINCT user_id) >= %(min_users)s` (or the aggregate's `unique_users` column).
4. `analytics.py`: `boston_analytics(repo, period, now)` in Python over the memory repo, with the same rules. The seed has only 3 users, so add 3 more demo users (`user-4` to `user-6`) to `rider_events.json` so some buckets pass the threshold and some do not. Keep the 006 hand-checked numbers for `user-1` valid.
5. Route in `routes/insights.py`.
6. Tests in `tests/test_boston_analytics.py`: shape matches the OpenAPI (reuse `tests/openapi_shape.py`), k-anonymity suppression (a stop visited by only 1-2 users never appears), change_pct math on a hand-built repo, no user ids anywhere in the response body (scan the JSON for `user-`), period default, and 401 without auth. Extend `tests/test_sql_files.py` to cover the new file.

## Acceptance criteria
- The spec validates at 0.2.0, and the conformance test from 008 (if present) covers the new route.
- No response exposes a user id or a bucket below 3 distinct users.
- `python -m pytest -q` passes.

## Tests to run
- `cd insights-sponsors && python -m pytest -q`

## Out of scope
- Running SQL against a database. Writing to `../contracts/`.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
