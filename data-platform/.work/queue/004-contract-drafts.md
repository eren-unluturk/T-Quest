---
id: 004
title: Draft schema contract doc and data-platform OpenAPI for publication
status: done
issue: 8
depends_on: [003]
---
## Goal
Produce the v0 schema contract and the read-API OpenAPI spec as drafts inside `data-platform/contracts-draft/`, ready for Eren to copy into `../contracts/db/` and `../contracts/api/data-platform.yaml`. (Builder must not write `../contracts/`; publication is a human step.)

## Context
- `../contracts/README.md` (what belongs in db/ and api/)
- `../contracts/api/game-engine.yaml` (style to match: OpenAPI 3.0.3, components/schemas, bearer auth)
- `migrations/0000_*.sql` to `0002_*.sql`
- `AGENT.md` endpoint list: GET /stops, /stops/{id}, /lines, /routes, /vehicles, /predictions, /alerts
- Planned realtime and aggregate tables (prompts 005, 006 in `.work/queue/`) so the doc lists them as "planned v0.1"

## Steps
1. `contracts-draft/db/SCHEMA.md`: one section per table (columns, types, keys, constraints, which agent reads/writes it), hypertables and chunk intervals, the points_ledger append-only rule, the `user_points`/`user_rank`/`active_consent` views, `expire_redemptions()`, and a "Planned (v0.1)" section for `vehicles`, `predictions`, `alerts`, `alert_entities`, and continuous aggregates `leaderboard_daily`, `home_line_weekly`/`home_line`, `personal_stats_daily` (names and purpose only, from prompts 005/006). Include a "Write ownership" table: game-engine writes rider_events, points_ledger, user_collections, redemptions, friends; insights-sponsors writes stop_facts, sponsors, stores, offers, rewards, quests, physical_rewards, store_inventory, consent; data-platform writes routes, stops, route_stops and realtime tables. Include "How to connect" (local compose and Tiger Cloud `DATABASE_URL`, run `python -m data_platform.migrate`).
2. `contracts-draft/db/schema.sql`: `pg_dump --schema-only --no-owner` of the migrated local DB (use the compose container: `docker compose exec db pg_dump ...`). Add a header comment that it is generated and that migrations in `data-platform/migrations/` are the source of truth.
3. `contracts-draft/api/data-platform.yaml`: OpenAPI 3.0.3, `info.version: 0.1.0`. Read endpoints are public (no auth; they serve no user data), state this in `info.description`. Paths:
   - `GET /health`
   - `GET /routes?mode=` -> Route[]
   - `GET /lines` -> Line[] (groups routes by `line_id`; subway lines plus a `bus` group summary)
   - `GET /stops?route_id=&lat=&lon=&radius_m=&limit=` -> Stop[]
   - `GET /stops/{id}` -> StopDetail (Stop + routes[] + facts[] + is_freedom_trail)
   - `GET /vehicles?route_id=&stop_id=&since_s=` -> Vehicle[] (latest position per vehicle; `stop_id` + `since_s` lets game-engine check "vehicle seen at stop within 300s")
   - `GET /predictions?stop_id=&route_id=` -> Prediction[]
   - `GET /alerts?route_id=&stop_id=&active=true` -> Alert[]
   Schemas: Route, Line, Stop, StopDetail, StopFact, Vehicle, Prediction, Alert, Error. 404 on unknown stop. Ids are MBTA string ids.
4. Validate the YAML: add `openapi-spec-validator` to dev deps and a test `tests/test_openapi_draft.py` that validates `contracts-draft/api/data-platform.yaml`.
5. `contracts-draft/PUBLISH.md`: the exact copy commands for Eren (PowerShell): `Copy-Item contracts-draft/db/* ../contracts/db/ -Force`; `Copy-Item contracts-draft/api/data-platform.yaml ../contracts/api/data-platform.yaml -Force`, then commit from repo root.

## Acceptance criteria
- SCHEMA.md covers every table and view in migrations 0000-0002 with no omissions (cross-check against `\dt` and `\dv`).
- schema.sql is regenerated from the current migrations.
- OpenAPI validates and lists all 8 paths.

## Tests to run
`pytest -q` (all previous tests plus the OpenAPI validation test).

## Out of scope
Implementing the endpoints (prompt 008). Writing into `../contracts/`.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
