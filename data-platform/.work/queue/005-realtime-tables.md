---
id: 005
title: MBTA realtime tables with compression and retention
status: ready
depends_on: [002]
---
## Goal
Hypertables for MBTA realtime vehicles and predictions with compression and retention policies, plus alert tables usable for home-line compensation.

## Context
- `../DECISIONS.md` D12 (demo numbers: compression ratio)
- MBTA V3 API resources: `/vehicles`, `/predictions`, `/alerts` (attributes: vehicle `current_status`, `latitude`, `longitude`, `bearing`, `speed`, `label`, `updated_at`, relationships route/trip/stop; prediction `arrival_time`, `departure_time`, `direction_id`, `status`, `schedule_relationship`; alert `effect`, `cause`, `severity`, `header`, `description`, `lifecycle`, `active_period[]`, `informed_entity[]`)
- `migrations/0001_core.sql`

## Steps
Create `migrations/0003_realtime.sql` (idempotent; use `-- migrate:no-transaction` only if a policy call requires it):
1. `vehicles` hypertable on `time` (poll time): `time timestamptz not null`, `vehicle_id text not null`, `route_id text`, `trip_id text`, `stop_id text`, `direction_id smallint`, `current_status text`, `lat double precision`, `lon double precision`, `bearing real`, `speed real`, `label text`, `updated_at timestamptz` (from MBTA). Unique `(vehicle_id, time)`. Chunk interval 1 day. Indexes `(stop_id, time desc)`, `(route_id, time desc)`.
2. `predictions` hypertable on `time`: `time timestamptz not null`, `prediction_id text not null`, `stop_id text`, `route_id text`, `trip_id text`, `direction_id smallint`, `arrival_time timestamptz`, `departure_time timestamptz`, `status text`, `schedule_relationship text`. Unique `(prediction_id, time)`. Chunk interval 1 day. Index `(stop_id, time desc)`.
3. Compression on both: `timescaledb.compress`, `compress_segmentby = 'route_id'`, `compress_orderby = 'time DESC'`. Policy: compress chunks older than 1 day. Retention: drop chunks older than 30 days.
4. `alerts` (regular table, upserted): `id text pk`, `effect`, `cause`, `severity int`, `header`, `description`, `lifecycle`, `active_start timestamptz`, `active_end timestamptz null`, `first_seen_at`, `last_seen_at`, `raw jsonb`.
5. `alert_entities`: `alert_id fk on delete cascade`, `route_id text null`, `stop_id text null`, `route_type int null`, `direction_id smallint null`. Index on `route_id`, `stop_id`.
6. View `active_alerts`: alerts whose active window contains `now()`.
7. `data-platform/src/data_platform/bench.py` stub with a function `compression_stats()` that returns `hypertable_compression_stats` for vehicles and predictions (before/after bytes and ratio). Full benchmark is prompt 010.

## Acceptance criteria
- Migration applies on top of 0002 and re-runs as a no-op.
- `timescaledb_information.jobs` shows compression and retention jobs for both hypertables.
- Inserting synthetic vehicle rows 2 days old, then `CALL run_job(<compression job id>)` compresses that chunk; `compression_stats()` returns a ratio > 1.
- `active_alerts` excludes expired alerts.

## Tests to run
`pytest -q`; add `tests/test_realtime_schema.py` for the criteria above (generate a few thousand synthetic rows).

## Out of scope
The ingestion worker (007). Continuous aggregates (006). Editing `../contracts/`.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
