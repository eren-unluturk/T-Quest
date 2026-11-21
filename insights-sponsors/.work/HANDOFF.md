# HANDOFF: insights-sponsors (builder side)

## Status
The in-memory service is complete and tested: 149 tests pass, 1 skipped (public route has no 401 case). Prompts 001-006, 008, 010-013 are done. Prompt 014 (Postgres backend) was interrupted with only its badge-rename step finished, parked on branch `wip/insights-sponsors-014`; main contains no half-done work. Nothing has run against a real database yet: there was no Docker or Postgres in this environment.

## Done (all on main, 013 is the last commit)
- 001 FastAPI scaffold, config (`.env` resolved from the repo root), dev bearer auth. `/health`.
- 002/011/012/013 OpenAPI draft `openapi/insights-sponsors.yaml`, now version 0.3.0 (13 paths, 14 operations). Not yet promoted to `contracts/api/` (human step, #26).
- 003 Models, `Repository` Protocol, `MemoryRepository`, seed JSON in `data/seed/`.
- 004 `GET /stops/{id}/facts`, `/stops/{id}/local-picks`, `/freedom-trail`, `/fun-facts` (no auth), `/offers` (eligibility via `eligibility.is_eligible`), `/physical-rewards/catalog`.
- 005 `GET/POST /consent`, `DELETE /consent/{scope}`; `consent.has_consent` / `require_consent`; policy version 2026-11-21 (409 on mismatch).
- 006 `GET /analytics/me`, `GET /recommendations`; SQL drafts in `sql/` (analytics_me, recs_unvisited_neighborhoods, recs_routes, recs_place_affinity). Place signals only after `has_consent`.
- 008 Contract conformance test over every operation, no route outside the contract, `.env` path fix, README "Run locally".
- 010 29 stops (19 neighborhoods, 5 bus-mode), coordinates verified with `scripts/verify_stops.py` against the MBTA V3 API (exit 0), 2 more stores/offers, events for users 1-6.
- 012 `GET /analytics/boston`, k-anonymity (min 3 riders), `sql/analytics_boston.sql`.
- 013 `POST/DELETE /place-visits` (consent-gated, coordinates rounded to 3 decimals, 90-day retention); revoking `place_visits` deletes stored visits.
- Reports: `.work/reports/001.md` to `013.md` (no 007, 009, 014).

## In progress / partial
- Prompt 014. Branch `wip/insights-sponsors-014` (pushed, one commit "WIP: 014 ...") has the badge id rename (`line-green-complete`, `freedom-trail`, `rank-3` and so on) in seed JSON and tests, `psycopg-pool` dependency and a `db` pytest marker. The queue file is back to `ready` with detailed "Resume notes" (migration facts, design for ids/postgres repo/composite repo/loader). To resume: `git merge wip/insights-sponsors-014` (or cherry-pick) on main, then follow the Steps in `queue/014-postgres-catalog-content-consent.md`.

## Remaining (priority order)
1. 014 Postgres backend for catalog, content, consent, place visits (blocks 016).
2. 015 Bus parity in seed, analytics and recommendations.
3. 016 Analytics, recommendations and Boston analytics on Postgres plus latency bench (needs data-platform aggregates).
4. 017 store_id validation and demo smoke script.
Next 3 queue prompts: 014, 015, 017 (016 depends on 014 and 015). 007 stays blocked/superseded, 009 cancelled.
Items that block other agents: promoting the OpenAPI draft (#26, human) blocks client-bryan (#8).

## Blockers and open issues
- #1 data-platform schema: migrations 0000-0006 exist in `data-platform/migrations`; `contracts/db/` is still empty. Postgres work reads their migrations directly.
- #5 game-engine: badge ids and the redemption split need reconciling (we now use DB-style slugs on the WIP branch).
- #8 client-bryan: waits on the promoted contract (human, #26).
- #23 history trailer on commit 6732e8d1f5: `check-attribution.mjs` fails on history; needs a human decision, builders do not rewrite history.
- #11 kickoff (human).

## Decisions made and deviations
- No pay-per-usage services (README "Scope for this hackathon"); LLM recommendation text left out.
- Rolling 7/30 day windows; weeks start Monday; scores in 0-1 (neighborhood 1/rank, route 0.8x, place 0.6x) with ties broken by id and a rounded sort key.
- `total_checkins` is also zeroed when fewer than 3 riders were active (012); previous period under 3 riders counts as no data (+100%).
- Seed facts and URLs were written from general knowledge (URLs not fetched); trail-site and store coordinates are approximate; stop coordinates and names are verified.
- `app.openapi()` is used to list served routes because `app.routes` holds lazy router wrappers in this FastAPI version.
- Bash heredocs with quotes fail in this environment; use Write/Edit for files.

## Risks for the demo/pitch
- No database run yet, so the Tiger Data story (compression, aggregate latency) has no numbers from this service. 016 is the prompt that produces them.
- Recommendations and analytics depend on seed data for three or six users; the demo needs consistent seeded rider events across services.
- Draft contract unpromoted: clients cannot generate from `contracts/` yet.
- Auth is dev mode only (token is the user id).

## How to resume
1. Delete the stop file: `Remove-Item .work/STOP` (from `insights-sponsors/`).
2. From the repo root: `node scripts/duo.mjs insights-sponsors builder` (and `planner` in a second pane).
3. First thing: `git merge wip/insights-sponsors-014`, run `python -m pytest -q` (expect 149 passed), then continue prompt 014 at Step 1 (`repo/ids.py`).
