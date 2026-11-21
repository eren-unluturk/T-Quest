---
id: 006
title: Continuous aggregates - leaderboard, home line, personal stats
status: done
issue: 4
depends_on: [002]
---
## Goal
Continuous aggregates and views that back leaderboards (global/friends/line, week/month/all), home-line detection for outage compensation, and personal stats.

## Context
- `../contracts/api/game-engine.yaml` `/leaderboards` (scope global|friends|line, period week|month|all; LeaderboardRow position/username/points)
- `migrations/0001_core.sql` (`points_ledger` with `route_id`, `rider_events`, `friends`, `users`)
- TimescaleDB constraint: continuous aggregates cannot use DISTINCT aggregates or window functions; build rankings in regular views on top.

## Steps
Create `migrations/0004_aggregates.sql` with first line `-- migrate:no-transaction`, idempotent (`CREATE MATERIALIZED VIEW IF NOT EXISTS`, `if_not_exists => true` on policies):
1. `leaderboard_daily` CAGG on `points_ledger`: `time_bucket('1 day', at) as day`, `user_id`, `route_id`, `sum(delta) filter (where delta > 0) as points_earned`, `count(*) as entries`. Real-time aggregation on (`materialized_only = false`). Refresh policy: start_offset 30 days, end_offset 1 hour, schedule 5 minutes.
2. Function `leaderboard(p_scope text, p_period text, p_user uuid default null, p_route text default null, p_limit int default 50)` returning `(position int, user_id uuid, username text, points bigint)`: sums `points_earned` over the period (week = last 7 days, month = last 30, all = everything), filters by friends of `p_user` (plus the user) for `friends`, by `route_id = p_route` for `line`, ranks with `rank()`.
3. `home_line_weekly` CAGG on `rider_events` where `event_type in ('checkin','ride_start')` and `route_id is not null`: `time_bucket('7 days', time) as week`, `user_id`, `route_id`, `count(*) as rides`. Refresh policy: start_offset 90 days, end_offset 1 hour, schedule 15 minutes.
4. View `home_line`: per user, the route with the most rides over the last 4 weeks, only if rides >= 5; `users.home_line_override` wins when set. Columns: `user_id, route_id, checkins_28d` (name requested by insights-sponsors in #22).
5. Function `users_affected_by_alert(p_alert_id text)` returning `user_id` of users whose `home_line.route_id` is in that alert's `alert_entities.route_id`. If prompt 005 has not run, guard with a note; 005 runs first in practice, so add `005` to your check: if `alert_entities` is missing, skip creating this function and say so in the report.
6. `personal_stats_daily` CAGG on `rider_events`: `time_bucket('1 day', time) as day`, `user_id`, `count(*) filter (where event_type='checkin') as checkins`, `count(*) filter (where mode='bus') as bus_events`, `count(*) filter (where mode in ('subway','light_rail')) as rail_events`. Refresh policy like leaderboard. Distinct-stop counts come from a regular view `user_stop_visits` (`user_id, stop_id, first_visit, visits`) over `rider_events`.
7. For insights-sponsors (#22): `user_stop_daily` CAGG on `rider_events` where `stop_id is not null`: `time_bucket('1 day', time) as bucket`, `user_id`, `stop_id`, `route_id`, `count(*) as visits`. `user_stop_hourly` CAGG: `time_bucket('1 hour', time) as bucket`, `stop_id`, `user_id`, `count(*) filter (where event_type='checkin') as checkins`. Regular view `stop_popularity_hourly` over `user_stop_hourly`: `bucket, stop_id, sum(checkins) as checkins, count(*) filter (where checkins > 0) as unique_users` (this is how we get unique users without DISTINCT in a CAGG). Refresh policies: start_offset 30 days, end_offset 1 hour, schedule 15 minutes.

## Acceptance criteria
- Migration applies after 0003 and re-runs as a no-op.
- With synthetic data (3 users, friendships, ledger rows across 2 routes and 40 days), `leaderboard('global','week')`, `('friends','month', user)`, `('line','all', null, 'Red')` return correct totals and positions (ties share a position).
- `home_line` picks the most-ridden route, respects the 5-ride minimum and the override.
- `users_affected_by_alert` returns only home-line users of the alerted route.
- `stop_popularity_hourly.unique_users` is 2 when two users check in at one stop in the same hour (one of them twice) and `checkins` is 3.
- Query on the CAGG is measurably faster than the equivalent raw query on 100k+ synthetic ledger rows; log both timings in the report (rough numbers are fine; full benchmark is 010).

## Tests to run
`pytest -q`; add `tests/test_aggregates.py`. Call `CALL refresh_continuous_aggregate(...)` in tests before asserting.

## Out of scope
Awarding compensation points (game-engine). API endpoints. Editing `../contracts/`.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
