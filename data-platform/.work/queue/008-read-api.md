---
id: 008
title: Implement the read API from the data-platform OpenAPI draft
status: done
issue: 8
depends_on: [004, 005]
---
## Goal
Implement every path in `contracts-draft/api/data-platform.yaml` (or `../contracts/api/data-platform.yaml` if it has been published; prefer the published one) in the FastAPI app.

## Context
- The OpenAPI file above (source of truth for shapes, params, status codes)
- `src/data_platform/app.py`, `db.py`
- `migrations/0001_core.sql`, `0003_realtime.sql` (`active_alerts`, `alert_entities`)

## Steps
1. Routers in `src/data_platform/routes/`: `routes.py` (/routes, /lines), `stops.py` (/stops, /stops/{id}), `realtime.py` (/vehicles, /predictions, /alerts).
2. `/stops` nearby search: when `lat`/`lon` given, filter with a bounding box first then order by haversine distance in SQL; default `radius_m=500`, `limit=50`, max 500.
3. `/vehicles`: latest row per `vehicle_id` within the last `since_s` seconds (default 120) using `DISTINCT ON (vehicle_id) ... ORDER BY vehicle_id, time DESC`, filtered by `route_id`/`stop_id`.
4. `/predictions`: latest poll's predictions for the stop/route with `arrival_time >= now()`; 422 if neither `stop_id` nor `route_id` given.
5. `/alerts`: from `active_alerts` (or all when `active=false`) joined to `alert_entities` filters.
6. Response models (pydantic) match the OpenAPI schemas exactly. Enable CORS for all origins (public read API).
7. Contract test: load the OpenAPI file, call each path with the dev seed, and validate responses against the schema (use `openapi-core` or `jsonschema` on the component schemas).

## Acceptance criteria
- All 8 paths respond per the spec on the dev seed; `/stops/{unknown}` returns 404.
- `/vehicles?stop_id=X&since_s=300` returns a vehicle inserted 200 s ago and not one inserted 400 s ago.
- Nearby search returns stops ordered by distance.

## Tests to run
`pytest -q`; add `tests/test_read_api.py` and `tests/test_contract.py`.

## Out of scope
Auth, write endpoints, caching.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
