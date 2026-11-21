---
id: 007
title: MBTA static loader and realtime ingestion worker
status: done
depends_on: [005]
---
## Goal
Load MBTA routes/stops/route_stops into the DB, and a polling worker that writes vehicles, predictions and alerts into the realtime tables.

## Context
- `.env.example` (`MBTA_API_KEY`, `MBTA_API_BASE`)
- `migrations/0001_core.sql` (routes, stops, route_stops), `migrations/0003_realtime.sql` (vehicles, predictions, alerts, alert_entities)
- MBTA V3 API (JSON:API): `GET /routes?filter[type]=0,1,3`, `GET /stops?filter[route]=<id>` (parent stations for rail; `filter[route_type]=3` for bus stops), `GET /route_patterns` or `GET /stops?filter[route]=X&filter[direction_id]=0|1` in order for `route_stops.stop_sequence`, `GET /vehicles?filter[route_type]=0,1,3`, `GET /predictions?filter[route]=...` (predictions require a filter; poll subway routes only by default), `GET /alerts?filter[datetime]=NOW`. Header `x-api-key`. Rate limit 1000 req/min with key.

## Steps
1. `src/data_platform/mbta.py`: async httpx client with `x-api-key`, base URL from env, simple retry with backoff on 429/5xx, and pure parse functions `parse_route`, `parse_stop`, `parse_vehicle`, `parse_prediction`, `parse_alert` (JSON:API resource -> dict matching table columns).
2. `src/data_platform/load_static.py` (`python -m data_platform.load_static`): upserts subway, light rail and bus routes, their stops (parent stations for rail, stops for bus), and `route_stops` with direction and sequence. Upsert = `INSERT ... ON CONFLICT DO UPDATE`. Print counts.
3. `src/data_platform/ingest.py` (`python -m data_platform.ingest [--once] [--interval 15]`): each cycle fetches vehicles (all modes), predictions for subway/light-rail routes, and alerts; inserts vehicles/predictions with `time = poll time` using `executemany` or COPY; upserts alerts and replaces their `alert_entities`; updates `last_seen_at`. Log per-cycle counts and duration. Survives a failed cycle (log and continue).
4. README: add "Load MBTA data" section.

## Acceptance criteria
- Parse functions are unit tested with recorded JSON fixtures in `tests/fixtures/mbta/` (capture a small real sample once; strip nothing secret, the responses contain none).
- With a real `MBTA_API_KEY` in `.env`: `load_static` loads all subway lines and > 1000 bus stops; `ingest --once` writes vehicles, predictions and alerts rows. If no key is available, record that in the report and rely on fixtures plus a test that runs one ingest cycle against a mocked httpx transport.
- Re-running `load_static` does not duplicate rows.

## Tests to run
`pytest -q`; add `tests/test_mbta_parse.py` and `tests/test_ingest_cycle.py` (mocked transport, DB fixture).

## Out of scope
Scheduling/deploying the worker beyond a CLI loop. Read API (008).

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
