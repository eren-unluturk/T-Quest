---
id: 006
title: Analytics and recommendations, SQL drafts plus in-memory implementation
status: ready
issue: 3
depends_on: [004, 005]
---
## Goal
`GET /analytics/me` and `GET /recommendations` work now on in-memory rider events. The real Tiger Data SQL (time_bucket and continuous-aggregate queries) is written out as `.sql` files, ready for 008 once data-platform publishes the schema (#1). The SQL is the deliverable judges see. The in-memory version only keeps the endpoints alive.

## Context
- `insights-sponsors/openapi/insights-sponsors.yaml` (`MyAnalytics`, `Recommendations`)
- `src/insights_sponsors/consent.py` (005): `has_consent` must gate any place-visit signal
- The schema request the planner sent to data-platform (GitHub issue titled "[insights-sponsors] Tables, columns and aggregates needed for analytics, recommendations, catalog, consent"; run `gh issue list --search "insights-sponsors Tables, columns"` to read it). Write the SQL against the table and column names in that issue. If data-platform has published `../contracts/db/` by the time you start, use that instead and list the differences in the report.

## Steps
1. `insights-sponsors/sql/`: one file per query with a header comment naming the tables and aggregates it reads.
   - `analytics_me.sql`: per-user totals for a period, weekly `time_bucket('1 week', time)` series from `user_stop_daily`, top stops, lines ridden, neighborhoods explored (join `stops.neighborhood`), and home line (from the home-line aggregate).
   - `recs_unvisited_neighborhoods.sql`: neighborhoods popular in `stop_popularity_hourly` over the last 30 days that the user has never visited, reachable on the user's lines ridden. Score = popularity rank.
   - `recs_routes.sql`: routes the user has not ridden that connect to their home line (via `route_stops`).
   - `recs_place_affinity.sql`: boosts stops near store categories the user visited. It reads `place_visits`. The file header states that it may run only after `has_consent(user, "place_visits")`.
   - Use named parameters `%(user_id)s`, `%(since)s` and `%(limit)s` (psycopg style).
2. `repo/base.py`: add `rider_events(user_id, since)` and `place_visits(user_id, since)`. The memory backend reads `data/seed/rider_events.json` (generate about 200 events for 3 demo users over 6 weeks across the seeded stops; `user-1` has a clear home line) and `data/seed/place_visits.json` (small).
3. `src/insights_sponsors/analytics.py`: compute `MyAnalytics` in Python from `rider_events`. Home line = the line with the most check-ins in the last 28 days, with at least 5.
4. `src/insights_sponsors/recommend.py`: compute recommendations with the same logic as the SQL files (unvisited neighborhoods, unridden connecting routes, plus place affinity only when `has_consent`). Mark a recommendation `sponsored: true` only when an active `sponsored_quest` offer exists at a store near the recommended stop. Ordering must not depend on sponsorship: sponsored items keep their organic rank.
5. Routes in `routes/insights.py`, registered in `create_app()`.
6. Tests: analytics numbers for `user-1` (hand-check a couple), home line detection, recommendations exclude visited neighborhoods, place-visit signal used only with consent (same user, before and after granting `place_visits`), sponsored flag never changes order, and 401 without auth. Add a test that each `.sql` file exists and contains `time_bucket` or reads a named aggregate. Do not run the SQL.

## Acceptance criteria
- Endpoints match the OpenAPI schema.
- No code path reads `place_visits` without `has_consent`; a test covers it.
- The SQL files are complete, commented, and parameterized.
- `pytest` passes.

## Tests to run
- `cd insights-sponsors && pytest -q`

## Out of scope
- Executing SQL against a database (008). AI/LLM-generated recommendation text (later, optional).

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
