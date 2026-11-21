---
id: 012
title: Add insights-sponsors aggregates and rename home_line count to checkins_28d
status: ready
issue: 22
depends_on: [006, 010]
---
## Goal
Prompt 006 was amended for #22 after the builder had started it, so `0004_aggregates.sql` lacks `user_stop_daily`, `user_stop_hourly` and `stop_popularity_hourly`, and `home_line` exposes `rides_28d` instead of the agreed `checkins_28d`. Add them in a new migration.

## Context
- Issue #22 (insights-sponsors reads these names)
- `migrations/0004_aggregates.sql` (home_line view ~line 75-95, users_affected_by_alert depends on home_line)
- `src/data_platform/migrate.py` (`-- migrate:no-transaction` splitting)
- `tests/test_aggregates.py` (home_line test selects rides_28d)

## Steps
Create the next free migration (expected `0006_insights_aggregates.sql`), first line `-- migrate:no-transaction`, idempotent:
1. `user_stop_daily` CAGG on `rider_events` where `stop_id is not null`: `time_bucket('1 day', time) as bucket`, `user_id`, `stop_id`, `route_id`, `count(*) as visits`. Refresh policy start_offset 30 days, end_offset 1 hour, schedule 15 minutes. `materialized_only = false`.
2. `user_stop_hourly` CAGG on `rider_events` where `stop_id is not null`: `time_bucket('1 hour', time) as bucket`, `stop_id`, `user_id`, `count(*) filter (where event_type = 'checkin') as checkins`. Same policy.
3. View `stop_popularity_hourly`: `bucket, stop_id, sum(checkins)::bigint as checkins, count(*) filter (where checkins > 0) as unique_users` from `user_stop_hourly` group by bucket, stop_id.
4. Rename `home_line.rides_28d` to `checkins_28d`: drop `users_affected_by_alert` (if exists), `DROP VIEW IF EXISTS home_line`, recreate `home_line` with identical logic but the new column name, then recreate `users_affected_by_alert` exactly as in 0004 (keep the `to_regclass` guard). Make the whole step safe to re-run.
5. Update `tests/test_aggregates.py` to use `checkins_28d`. Add `tests/test_insights_aggregates.py`: two users check in at one stop in the same hour (one twice) -> `stop_popularity_hourly` has checkins 3, unique_users 2 after `refresh_continuous_aggregate`; `user_stop_daily.visits` counts per user/stop/day.
6. Update `contracts-draft/db/SCHEMA.md` (aggregates section and the #22 name table) and `schema.sql` to include this migration.

## Acceptance criteria
- Migration applies after 0005 and re-runs as a no-op.
- `home_line` has columns `user_id, route_id, checkins_28d`; `users_affected_by_alert` still works.
- Popularity test values as above.
- No other test references `rides_28d`.

## Tests to run
`pytest -q` (DB tests skip without a DB; the splitter tests must still pass).

## Out of scope
Benchmarks (009). Editing `../contracts/`.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
