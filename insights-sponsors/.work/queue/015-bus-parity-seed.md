---
id: 015
title: Bus parity in seed data, analytics and recommendations
status: ready
issue:
depends_on: [013]
---
## Goal
The brief says T-Quest covers subway and bus equally. The seed has 5 bus-mode stops but no bus routes or rider events (report 010), so bus riders get nothing from analytics or recommendations. Add bus routes and events, and make sure the logic treats bus like rail.

## Context
- Report `.work/reports/010.md` (bus stop ids: 79 on Route 1, 1720 on Route 28, 1164 on Route 39, 10928 on Route 66, plus `place-crtst` Silver Line)
- `insights-sponsors/data/seed/route_stops.json`, `rider_events.json`, `stops.json`
- `src/insights_sponsors/analytics.py`, `recommend.py`
- `../data-platform/migrations/0004_aggregates.sql` (`personal_stats_daily` splits `bus_events` / `rail_events` by `mode`)

## Steps
1. `route_stops.json`: add routes `1`, `28`, `39`, `66` and `SL1` (or the Silver Line route serving `place-crtst`, checked with `https://api-v3.mbta.com/routes?filter[stop]=place-crtst`), each with its seeded bus stop. Also add any seeded subway stop the route really serves, confirmed via `https://api-v3.mbta.com/stops?filter[route]=<id>` (free API; this is a manual step and is not called from tests).
2. `rider_events.json`: add a bus commuter `user-7` whose home line is a bus route (for example `28`, with 5 or more check-ins in the last 28 days, `mode: "bus"`), and a few bus events for `user-2`. Keep the existing hand-checked numbers for `user-1` and for the 012 Boston tests valid; if one must change, update it and explain why.
3. Check `analytics.py` and `recommend.py` for rail-only assumptions (mode filters, route id patterns such as `Red`/`Green`). Remove them so a bus route can be a home line, a ridden line and a recommended route.
4. Tests: `user-7`'s home line is `28`, `lines_ridden` includes bus routes, `/recommendations` can return a bus `route` item for a rail-only user whose network touches a bus stop, and Boston analytics `lines` includes bus routes when they pass the k-anonymity threshold.

## Acceptance criteria
- A bus-only rider gets non-empty analytics and recommendations.
- `python -m pytest -q` passes.

## Tests to run
- `cd insights-sponsors && python -m pytest -q`

## Out of scope
- Realtime bus data (data-platform). Contract changes.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
