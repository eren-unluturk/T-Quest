---
id: 012
title: Add insights-sponsors aggregates and align home_line with game-engine (checkins_30d)
status: done
issue: 22
depends_on: [006, 010]
---
## Goal
Prompt 006 was amended for #22 after the builder had started it, so `0004_aggregates.sql` lacks `user_stop_daily`, `user_stop_hourly` and `stop_popularity_hourly`, and `home_line` (28-day, bucket-aligned, no tie-break) does not match game-engine's rule in `delay.py` (30 days, ties to most recent). Count column becomes `checkins_30d` (insights-sponsors asked for `checkins_28d`; the planner tells them on #22). Add them in a new migration.

## Context
- Issue #22 (insights-sponsors reads these names)
- `migrations/0004_aggregates.sql` (home_line view ~line 75-95, users_affected_by_alert depends on home_line)
- `src/data_platform/migrate.py` (`-- migrate:no-transaction` splitting)
- `tests/test_aggregates.py` (home_line test selects rides_28d)
- `../game-engine/src/game_engine/delay.py` (home_line rule: HOME_LINE_WINDOW_DAYS=30, HOME_LINE_MIN_RIDES=5, tie to most recent ride)

## Steps
Create the next free migration (expected `0006_insights_aggregates.sql`), first line `-- migrate:no-transaction`, idempotent:
1. `user_stop_daily` CAGG on `rider_events` where `stop_id is not null`: `time_bucket('1 day', time) as bucket`, `user_id`, `stop_id`, `route_id`, `count(*) as visits`. Refresh policy start_offset 30 days, end_offset 1 hour, schedule 15 minutes. `materialized_only = false`.
2. `user_stop_hourly` CAGG on `rider_events` where `stop_id is not null`: `time_bucket('1 hour', time) as bucket`, `stop_id`, `user_id`, `count(*) filter (where event_type = 'checkin') as checkins`. Same policy.
3. View `stop_popularity_hourly`: `bucket, stop_id, sum(checkins)::bigint as checkins, count(*) filter (where checkins > 0) as unique_users` from `user_stop_hourly` group by bucket, stop_id.
4. Rebuild `home_line` to match game-engine's rule (`../game-engine/src/game_engine/delay.py`: last 30 days, min 5 rides, ties go to the line ridden most recently) and rename the count to `checkins_30d`. Add CAGG `user_route_daily` on `rider_events` where `event_type in ('checkin','ride_start') and route_id is not null`: `time_bucket('1 day', time) as bucket`, `user_id`, `route_id`, `count(*) as rides`, `max(time) as last_ride`; same refresh policy, `materialized_only = false`. Then: drop `users_affected_by_alert` (if exists), `DROP VIEW IF EXISTS home_line`, recreate `home_line` from `user_route_daily` where `bucket >= time_bucket('1 day', now() - interval '30 days')`: per user pick the route with max `sum(rides)`, tie-break max `max(last_ride)`, keep only `sum(rides) >= 5`; `users.home_line_override` still wins. Columns `user_id, route_id, checkins_30d`. Recreate `users_affected_by_alert` exactly as in 0004 (keep the `to_regclass` guard). Leave `home_line_weekly` in place (personal stats may use it). Make the whole step safe to re-run.
5. Update `tests/test_aggregates.py` to use `checkins_30d`, and add a tie-break test (two routes with equal rides, the more recently ridden wins) and a window test (rides 31+ days old ignored). Add `tests/test_insights_aggregates.py`: two users check in at one stop in the same hour (one twice) -> `stop_popularity_hourly` has checkins 3, unique_users 2 after `refresh_continuous_aggregate`; `user_stop_daily.visits` counts per user/stop/day.
6. Update `contracts-draft/db/SCHEMA.md` (aggregates section and the #22 name table) and `schema.sql` to include this migration.

## Acceptance criteria
- Migration applies after 0005 and re-runs as a no-op.
- `home_line` has columns `user_id, route_id, checkins_30d`, matches delay.py on window, minimum and tie-break; `users_affected_by_alert` still works.
- Popularity test values as above.
- No other test references `rides_28d`.

## Tests to run
`pytest -q` (DB tests skip without a DB; the splitter tests must still pass).

## Out of scope
Benchmarks (009). Editing `../contracts/`.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
