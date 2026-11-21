---
id: 003
title: Pydantic models, repository interface, in-memory backend and seed content
status: ready
issue:
depends_on: [002]
---
## Goal
Typed models that match the OpenAPI draft, a repository interface with an in-memory backend loaded from seed JSON, and real Boston seed content (stop facts, Freedom Trail, fun facts, sponsors, stores, offers, physical rewards). The endpoints (004, 005) run fully before the Tiger Data schema (#1) lands. A Postgres backend replaces the in-memory one later (008).

## Context
- `insights-sponsors/openapi/insights-sponsors.yaml` (from 002). The models must match it field for field.
- `../contracts/api/game-engine.yaml` `x-rules.ranks` (ranks 1-5).
- `../docs/PROJECT_BRIEF.md` (tourist layer, sponsors, physical rewards).

## Steps
1. `src/insights_sponsors/models.py`: Pydantic v2 models for every schema in the OpenAPI draft. Use the same names.
2. `src/insights_sponsors/repo/base.py`: a `Repository` Protocol with: `get_stop(stop_id)`, `stop_facts(stop_id)`, `stores_near_stop(stop_id, limit)` (returns `(StorePartner, distance_m)` pairs), `offers(stop_id=None, store_id=None, category=None)`, `physical_rewards()`, `trail_sites()`, `fun_facts()`, `get_consents(user_id)`, `set_consent(user_id, scope, granted, policy_version)`, `user_rank(user_id)` and `user_badges(user_id)`. Return models, not dicts.
3. `src/insights_sponsors/repo/memory.py`: `MemoryRepository` that loads `insights-sponsors/data/seed/*.json` once. It keeps consents in a dict. `user_rank` defaults to 1 and `user_badges` to empty, overridable through a `set_user_profile(user_id, rank, badges)` helper for tests. Distance uses the haversine formula on lat/lon.
4. `src/insights_sponsors/repo/__init__.py`: `get_repository()` FastAPI dependency. It returns a process-wide `MemoryRepository` when `data_backend == "memory"`, and raises `NotImplementedError` for `postgres` (008 adds that).
5. Seed JSON in `insights-sponsors/data/seed/`:
   - `stops.json`: at least 12 real MBTA stops with real MBTA stop ids (parent stations such as `place-pktrm` Park Street, `place-dwnxg` Downtown Crossing, `place-gover` Government Center, `place-state` State, `place-haecl` Haymarket, `place-north` North Station, `place-coecl` Copley, `place-harsq` Harvard, `place-kencl` Kenmore, `place-sstat` South Station, `place-bbsta` Back Bay, `place-aqucl` Aquarium) with name, lat, lon and neighborhood.
   - `stop_facts.json`: 2-3 facts per stop (fast_fact/history; freedom_trail where it applies). Facts must be accurate and well known. Add a `source_url` (Wikipedia or nps.gov) where you can.
   - `freedom_trail.json`: all 16 official Freedom Trail sites in order, with lat/lon, nearest_stop_id from the stops above, and a one-sentence blurb.
   - `fun_facts.json`: 25 short Boston/MBTA facts with tags (for example: the Tremont Street Subway opened in 1897 as the first subway in the US).
   - `sponsors.json`, `stores.json`, `offers.json`: clearly fictional demo businesses (no real brand names or logos; names like "Demo Cafe Park St"). 8 stores across food, clothing and sports near the seeded stops, and 12 offers that cover every `kind`, ranks 1-5, one with `required_badge_id`, and both placements.
   - `physical_rewards.json`: 6 items (for example: Green Line completion patch, Freedom Trail sticker, rank 3/4/5 patches, Red Line sticker), each with a `badge_id` (use readable ids such as `badge.line.green.complete`; game-engine owns the real ids, so list the ids you used in the report) and stock per store as `stores`.
6. `tests/test_memory_repo.py`: seed loads, every fact and trail site references a seeded stop, offers reference existing stores and sponsors, `stores_near_stop` is sorted by distance, and consent set/revoke round-trips.

## Acceptance criteria
- All seed files parse into the models. Referential integrity is checked by the tests.
- No real sponsor or brand names appear in sponsors, stores or offers.
- `pytest` passes.

## Tests to run
- `cd insights-sponsors && pytest -q`

## Out of scope
- HTTP routes (004/005), Postgres (008), recommendations and analytics.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
