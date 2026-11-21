---
id: 002
title: Draft the insights-sponsors OpenAPI v0
status: done
issue: 8
depends_on: [001]
---
## Goal
A valid OpenAPI 3.0.3 draft for every insights-sponsors endpoint, so client-bryan (#8) and game-engine (#5) can build against it. The builder writes it inside our folder. The human (Eren) promotes it to `contracts/api/insights-sponsors.yaml`, because builders never write to `contracts/`.

## Context
- `AGENT.md` (endpoints we own)
- `../docs/PROJECT_BRIEF.md` (sponsors, physical rewards, tourist layer, analytics, consent)
- `../contracts/api/game-engine.yaml`: copy its style (servers, `bearerAuth`, `x-rules`, inline `{$ref: ...}`). Note its `x-rules.ranks` (rank 1-5, discount_pct) and `redemption_limits`. Game-engine owns code issuing (`POST /redemptions`) and store verification (`POST /redemptions/verify`). We own the catalog those routes reference by `offer_id`.
- GitHub issue #8 (auth assumptions: bearer token, user id from session, location only with consent, 403 otherwise).

## Steps
1. Create `insights-sponsors/openapi/insights-sponsors.yaml`. `servers: [{url: http://localhost:8002}]`, global `security: [bearerAuth: []]`, version `0.1.0`. In the description, mark it DRAFT, say that game-engine owns redemption issuing and verification, and that rank and discount numbers come from `game-engine.yaml` `x-rules.ranks`.
2. Paths (all bearer-auth unless noted):
   - `GET /stops/{stop_id}/facts` -> `StopFacts` {stop_id, stop_name, facts: [Fact {id, kind: enum[fast_fact, history, freedom_trail], title, body, source_url nullable}]}. 404 for an unknown stop.
   - `GET /stops/{stop_id}/local-picks` -> array of `LocalPick` {store: StorePartner, offers: [Offer], distance_m}. Query `limit` (default 5, max 20). These are native placements, never pop-ups (put that in the description).
   - `GET /freedom-trail` -> array of `TrailSite` {id, order, name, lat, lon, nearest_stop_id, blurb}.
   - `GET /fun-facts` -> array of `FunFact` {id, body, tags[]}. Query `limit` (default 10), `random` (bool, default true). Mark `security: []` (loading screen, before login).
   - `GET /offers` -> array of `Offer`. Query `stop_id`, `store_id`, `category` (enum food, clothing, sports, other), `eligible_only` (bool, default false; when true, only offers the caller's rank and badges qualify for).
   - `GET /physical-rewards/catalog` -> array of `PhysicalReward` {id, kind: enum[sticker, patch], name, description, badge_id, min_rank, per_user_limit, image_url nullable, stores: [{store_id, in_stock: bool}]}.
   - `GET /recommendations` -> `Recommendations` {generated_at, items: [Recommendation {kind: enum[route, neighborhood, stop], id, title, reason, score, sponsored: bool, sponsor_id nullable}]}. Query `kind`, `limit` (default 5). Description: SQL-based over Tiger Data aggregates. Place-visit signals are used only when the `place_visits` consent is granted.
   - `GET /analytics/me` -> `MyAnalytics` {user_id, period, stops_visited, unique_stops, lines_ridden[], home_line nullable, by_week: [{week_start, checkins, unique_stops}], top_stops: [{stop_id, visits}], neighborhoods_explored[]}. Query `period` enum[week, month, all] (default month).
   - `GET /consent` -> array of `Consent` {scope: enum[location, place_visits], granted: bool, granted_at nullable, revoked_at nullable, policy_version}.
   - `POST /consent` body `ConsentRequest` {scope, policy_version} -> 201 `Consent`.
   - `DELETE /consent/{scope}` -> 200 `Consent` (granted false). Revoking `place_visits` stops future use and makes stored place-visit data ineligible for recommendations.
3. Schemas `Offer` {id, sponsor_id, store_id, title, description, kind: enum[discount, free_item, points_item], discount_pct nullable, points_cost nullable, min_rank (int 1-5), required_badge_id nullable, per_user_limit, starts_at, ends_at nullable, placement: enum[local_pick, sponsored_quest]}, `StorePartner` {id, name, category, lat, lon, nearest_stop_id, address}, and `Error` {detail}. Add 401 on all authed routes.
4. Create `tests/test_openapi.py`: loads the YAML, validates it with `openapi_spec_validator.validate`, and asserts that every path listed in step 2 is present with the stated method.
5. Add a short "Contract" section to `insights-sponsors/README.md`: the draft lives in `openapi/` until it is promoted to `contracts/api/insights-sponsors.yaml`.

## Acceptance criteria
- The YAML validates and the tests pass.
- Every path, query parameter and schema above is present, with field names exactly as written (clients generate from them).
- Nothing written under `../contracts/`.

## Tests to run
- `cd insights-sponsors && pytest -q`

## Out of scope
- Implementing any endpoint. Redemption routes (game-engine owns them). Copying into `contracts/`.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
