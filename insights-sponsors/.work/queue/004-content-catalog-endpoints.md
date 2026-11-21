---
id: 004
title: Implement content and catalog endpoints
status: done
issue: 5
depends_on: [003]
---
## Goal
Serve the tourist content and the sponsor/reward catalog from the repository, exactly as the OpenAPI draft defines them.

## Context
- `insights-sponsors/openapi/insights-sponsors.yaml`
- `src/insights_sponsors/models.py`, `repo/` (from 003), `auth.py` (from 001)
- `../contracts/api/game-engine.yaml` `x-rules.ranks` (eligibility uses rank, not discount_pct)

## Steps
1. `src/insights_sponsors/routes/content.py`: `GET /stops/{stop_id}/facts` (404 `{"detail":"unknown stop"}`), `GET /freedom-trail` (sorted by `order`), and `GET /fun-facts` (no auth; `limit` 1-50, default 10; `random=true` shuffles, `random=false` keeps seed order).
2. `src/insights_sponsors/routes/catalog.py`:
   - `GET /stops/{stop_id}/local-picks`: nearest stores (limit 1-20, default 5), each with its currently active offers (`starts_at <= now` and (`ends_at` null or `> now`)) where `placement == "local_pick"`. Leave out stores with no active offers. 404 for an unknown stop.
   - `GET /offers`: filters `stop_id` (offers at stores whose `nearest_stop_id` matches), `store_id`, `category`, `eligible_only`. Eligibility: `user_rank >= min_rank` and (`required_badge_id` null or in `user_badges`).
   - `GET /physical-rewards/catalog`: all items, with `in_stock` per store.
3. Put the eligibility check in `src/insights_sponsors/eligibility.py` as a pure function `is_eligible(offer, rank, badges) -> bool`, so game-engine's redemption logic can mirror it.
4. Register the routers in `create_app()`. All routes except `/fun-facts` and `/health` require `current_user_id`.
5. Tests in `tests/test_content.py` and `tests/test_catalog.py`: happy path per route, 404s, 401 without auth, `/fun-facts` works without auth, `eligible_only` with rank 1 vs rank 5 (use `set_user_profile`), the badge-gated offer, and expired offers excluded from local picks.
6. Add a test that every response from these routes validates against the matching OpenAPI schema. Either load the schema from the YAML and validate with `jsonschema`, or compare the response keys with the schema properties. Pick the simpler option and say which in the report.

## Acceptance criteria
- Responses match the OpenAPI field names exactly.
- The sponsor placement appears only inside local picks or offers lists. No other endpoint injects sponsor content.
- `pytest` passes.

## Tests to run
- `cd insights-sponsors && pytest -q`

## Out of scope
- Redemption and code issuing (game-engine). Consent (005). Recommendations and analytics (006/007).

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
