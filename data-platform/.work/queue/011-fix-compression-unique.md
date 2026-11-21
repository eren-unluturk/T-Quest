---
id: 011
title: Make realtime compression settings compatible with the unique indexes
status: done
depends_on: [005]
---
## Goal
TimescaleDB refuses to enable compression on a hypertable with a unique index unless every unique-index column is a segmentby or orderby column. `vehicles` has unique `(vehicle_id, time)` and `predictions` has unique `(prediction_id, time)`, but both compress with `segmentby = 'route_id'`, `orderby = 'time DESC'`, so `0003_realtime.sql` will fail on a real database. Keep the unique indexes (ingestion uses them for de-duplication) and fix the compression settings.

## Context
- `migrations/0003_realtime.sql` (lines ~40-56)
- Report 005 (Deviations, unique index risk)
- No database has applied 0003 yet (no DB exists, issue #25), so edit 0003 in place instead of adding a new migration.

## Steps
1. In `0003_realtime.sql`: `vehicles` -> `compress_segmentby = 'route_id'`, `compress_orderby = 'vehicle_id, time DESC'`. `predictions` -> `compress_segmentby = 'route_id'`, `compress_orderby = 'prediction_id, time DESC'`.
2. Add a comment above each ALTER explaining why the id is in orderby.
3. If `contracts-draft/db/schema.sql` contains 0003, update it to match.
4. Add a test in `tests/test_realtime_schema.py` that reads `timescaledb_information.compression_settings` and asserts `vehicle_id`/`prediction_id` appear as orderby columns (skips without a DB). Also add a pure-text test that parses 0003 and asserts every unique-index column of each compressed table appears in its segmentby or orderby list (runs without a DB).

## Acceptance criteria
- The text test passes without a DB.
- On a real DB (when available) 0003 applies and the compression job compresses a 2-day-old chunk.

## Tests to run
`pytest -q`

## Out of scope
Changing retention or chunk intervals.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
