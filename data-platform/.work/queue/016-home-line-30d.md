---
id: 016
title: Align home_line with game-engine delay.py (30 days, tie to most recent, checkins_30d)
status: ready
issue: 4
depends_on: [013]
---
## Goal
Prompt 012 was amended (commit 7d93b8b) before it was built, but report 012 implemented the earlier text: `home_line` still uses 28 bucket-aligned days, has no tie-break, and exposes `checkins_28d`. game-engine's rule (`../game-engine/src/game_engine/delay.py`) is: rides in the last 30 days, at least 5 on the line, ties go to the line ridden most recently. Insights-sponsors (#22) and game-engine (#4) have already been told the column is `checkins_30d`. Re-read this file before starting; do not work from memory of 012.

## Context
- `../game-engine/src/game_engine/delay.py` (`home_line`, HOME_LINE_WINDOW_DAYS=30, HOME_LINE_MIN_RIDES=5)
- `migrations/0004_aggregates.sql` (home_line_weekly, users_affected_by_alert), `migrations/0006_insights_aggregates.sql` (current home_line)
- `tests/test_aggregates.py`, `tests/test_insights_aggregates.py`, `tests/test_sql_syntax.py`
- `src/data_platform/bench.py` (raw home-line comparison query)

## Steps
Create `migrations/0007_home_line_30d.sql`, first line `-- migrate:no-transaction`, idempotent:
1. CAGG `user_route_daily` on `rider_events` where `event_type in ('checkin','ride_start') and route_id is not null`: `time_bucket('1 day', time) as bucket`, `user_id`, `route_id`, `count(*) as rides`, `max(time) as last_ride`. `materialized_only = false`. Refresh policy: start_offset 40 days, end_offset 1 hour, schedule 15 minutes, `if_not_exists => true`.
2. `DROP FUNCTION IF EXISTS users_affected_by_alert(text)`; `DROP VIEW IF EXISTS home_line`; `CREATE OR REPLACE VIEW home_line` from `user_route_daily` where `bucket >= time_bucket('1 day', now() - interval '30 days')`: per user and route `sum(rides) as checkins_30d`, `max(last_ride) as last_ride`; per user keep the route with the highest `checkins_30d`, ties by latest `last_ride`, then `route_id`; keep only `checkins_30d >= 5`. `users.home_line_override` wins when set (its `checkins_30d` is the user's count on that route, 0 if none). Columns exactly `user_id, route_id, checkins_30d`.
3. Recreate `users_affected_by_alert` as in 0004/0006 (same signature and `to_regclass` guard).
4. Leave `home_line_weekly` in place.
5. Tests: update home_line assertions to `checkins_30d`; add a tie-break test (two routes with 5 rides each, the more recently ridden wins), a window test (rides 31 days old are ignored, 29 days old count), and the override test. Update `bench.py`'s raw home-line query to the same rule and alias.
6. Update `contracts-draft/db/SCHEMA.md` (home_line section, #22 name table: `checkins_30d`) and regenerate `schema.sql` with `python -m data_platform.concat_schema`.

## Acceptance criteria
- `tests/test_sql_syntax.py` passes with 0007 included (syntax and idempotency checks).
- No code, test or contract draft refers to `checkins_28d` except migrations 0006 and earlier and reports.
- `home_line` columns are `user_id, route_id, checkins_30d`.

## Tests to run
`pytest -q`

## Out of scope
Awarding compensation (game-engine). Editing `../contracts/`.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
