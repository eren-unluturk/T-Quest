# HANDOFF: insights-sponsors (updated 2026-11-21, unattended run)

## Latest (read this first)
- wip branch work is on main. Postgres backend now serves stops, offers, physical rewards, nearby spots, tourist content (`DATA_BACKEND=postgres`, run with a stale shell DATABASE_URL unset). Consent, place visits, analytics and recommendations still use memory (prompts 015-017 remain).
- New: nearby spots (`/stops/{id}/nearby`, `/categories`, `/labels`, `/spots/{id}`), `/rank-tiers`, `/offers?rank=&placement=`, `/stops/{id}/content`, `/loading-facts`. Contract v0.5.0 is in contracts/api/insights-sponsors.yaml.
- Load data: `python scripts/load_seed.py` then `python -m ingest_content.run` (both idempotent). Tests: `python -m pytest -q` (195 pass; db tests need migration 0010/0011 and a reachable database).
- Label rule: only declared or certified labels are exposed; the three demo sponsors hold local-independent as pending, so no real business shows a label.
- Not pursuing real partnerships; all sponsors are demo placeholders. A historic-inventory source was dropped; ingestion User-Agent is `T-Quest-Hackathon/1.0` with no contact details.

## Earlier handoff (2026-11-21 13:17)

## Status
The insights-sponsors service runs fully on the in-memory backend with real Boston seed data. Every route in the OpenAPI draft (v0.3.0, 14 operations) is implemented and checked by a conformance test, and 149 tests pass. That covers content, catalog, consent, place visits, personal analytics, Boston analytics and recommendations. The Tiger Data (Postgres) backend has not been built yet. Prompt 014 was interrupted early, its partial work is on a wip branch, and 015-017 are queued and not started. The contract is still a draft inside our folder and waits on a human to copy it into `contracts/` (#26).

## Done (built and verified)
- 001 FastAPI skeleton: `src/insights_sponsors/{main,config,auth}.py`, `GET /health`, port 8002. Dev auth treats the bearer token as the user id.
- 002, 011, 012, 013 OpenAPI draft `openapi/insights-sponsors.yaml` v0.3.0 (validated, changelog in `info.x-changelog`).
- 003 models, repository Protocol, memory backend, seed JSON in `data/seed/` (stops, facts, Freedom Trail, fun facts, fictional sponsors, stores, offers, physical rewards).
- 004 `GET /stops/{id}/facts`, `/stops/{id}/local-picks`, `/freedom-trail`, `/fun-facts` (no auth), `/offers` (with `eligible_only`), `/physical-rewards/catalog`. Eligibility rule in `eligibility.py` (agreed with game-engine on #5).
- 005 `GET/POST /consent`, `DELETE /consent/{scope}`. Single gate `consent.py` (`has_consent`, `require_consent`). Policy version 409.
- 006 `GET /analytics/me`, `GET /recommendations` (deterministic, sponsorship never changes order, place signals only with consent). SQL drafts in `sql/` (analytics_me, recs_*).
- 008 conformance test (every YAML operation vs the live app, no extra routes); `.env` resolved from the package path.
- 010 29 stops verified against the MBTA V3 API (`scripts/verify_stops.py`), 19 neighborhoods, 5 bus-mode stops.
- 012 `GET /analytics/boston` with k-anonymity (buckets under 3 riders hidden), plus `sql/analytics_boston.sql`.
- 013 `POST /place-visits` (consent-gated, coordinates rounded, 90-day retention) and `DELETE /place-visits`. Revoking consent deletes visits.
- Reports for each are in `.work/reports/NNN.md`. Issue #3 is closed.

## In progress / partial
- **014 Postgres backend (catalog, content, consent, place visits)**. Branch `wip/insights-sponsors-014` (pushed, commit ed294ec) holds only:
  - the badge-slug rename in the seed and tests
  - the `psycopg-pool` dependency and a `db` pytest marker (149 tests pass on it)

  Resume:
  1. Merge or cherry-pick ed294ec into main.
  2. Follow "Resume notes" in `.work/queue/014-postgres-catalog-content-consent.md`. They hold the worked-out design: uuid5 ids, `resolve_user`, a composite repo for insights routes, and the schema quirks (`stores.sponsor_id NOT NULL`, generated `consent.granted`, and others).

  The queue file is back to `ready`, with its resume notes committed on main.

## Remaining (priority order)
1. **HUMAN #26:** copy `insights-sponsors/openapi/insights-sponsors.yaml` (main, v0.3.0) to `contracts/api/insights-sponsors.yaml` and commit it. Blocks client-bryan (#8).
2. **014** Postgres backend for catalog, content, consent and place visits (resume from the wip branch). Next queue prompt.
3. **015** Bus parity: bus routes and events, and a bus home line in analytics and recs.
4. **016** Analytics, recs and Boston analytics on Postgres, plus `scripts/bench_queries.py` and `docs/bench.md` latency numbers (the Tiger Data demo angle). Needs a local TimescaleDB.
5. **017** `store_id` validation on place visits (avoids a 500 on a bad uuid in postgres mode) and `scripts/demo_smoke.py` for the presentation.
- Later, free only: aggregate-vs-raw demo numbers with data-platform. Out of scope (pay-per-usage): AI-written recommendation text (009, cancelled), paid Tiger tiers, and paid geocoding.

Next 3 queue prompts: **014, 015, 016** (017 depends on 016). 007 is superseded and 009 cancelled. Blocking other agents: #26 (human promotion) blocks client-bryan (#8).

## Blockers and open issues
- **#26** (to:humans) Eren promotes our OpenAPI draft into contracts/. Waiting on the human.
- **#23** (to:humans) commit 6732e8d (PR #19 squash) has a co-author trailer, so the doctor attribution check fails on history. Decide: rewrite and force-push, or allowlist. Waiting on the human.
- **#8** (from client-bryan) wants our OpenAPI. Acked, and the draft is announced at 0.3.0. Close after #26.
- **#5** (from game-engine) redemption split. Agreed: game-engine owns redemptions and verify; we own the catalog and eligibility. Ranks are 3/5/7/10/12%, game-engine is on port 8003, and badge slugs are shared (PR #31). Open point: game-engine has **no rank-4 badge**, but our seed has a rank-4 patch. Decide whether to drop it or ask them for one, then close #5.
- **#1** (from data-platform) v0 schema. Acked. The schema exists as a draft in `data-platform/contracts-draft/db/` (migrations 0000-0006) and is not yet in contracts/ (human step, see `data-platform/contracts-draft/PUBLISH.md`).
- **#22** (ours, to data-platform) columns and aggregates. Delivered in migrations 0005/0006. Open: the name conflict below.
- **#11** kickoff: Eren's GitHub handle in TEAM.md and team.json is still TODO (human).

## Decisions made and deviations from plan
- Builders cannot write `contracts/`, so the spec lives in `openapi/` until a human copies it.
- The in-memory backend comes first, so the API was demoable before the schema existed. Postgres comes after (014/016). 007 is superseded by 014.
- No pay-per-usage this hackathon. 009 (LLM reasons) is cancelled, and recommendations stay deterministic SQL. The scope rule is at the top of ROADMAP.md.
- Privacy: k-anonymity of 3 for city analytics (totals and baselines included), coordinates rounded to about 100 m, 90-day retention, revoke deletes visits, deletion always allowed.
- DB ids are uuid. Seed slugs map with uuid5 (deterministic). Badge ids use the data-platform/game-engine slugs (`line-red-complete`, `freedom-trail`, `rank-3`).
- Rank 1 discount is 3% (game-engine's call), not about 5% as in the brief.
- From the builder: rolling 7/30-day windows; weeks start Monday; scores in 0-1 (neighborhood 1/rank, route 0.8x, place 0.6x) with ties broken by id and a rounded sort key. `app.openapi()` lists served routes, because `app.routes` holds lazy router wrappers in this FastAPI version. Bash heredocs with quotes fail in this environment, so use Write/Edit for files.

## Risks for the demo/pitch
- **No Postgres has run our code yet.** No Docker was available to the builder, data-platform's migration 0006 has never run against a DB, and the latency numbers (016) don't exist yet. The Tiger Data prize story depends on 014 and 016 plus a local TimescaleDB.
- **home_line column name conflict:** data-platform's latest #22 comment says `checkins_30d` (30-day window), while migration 0006 creates `checkins_28d`. Check the real column before 016.
- The contract is not in contracts/ yet (#26), so clients may build against a moving draft.
- Seed facts were written from general knowledge, and their source URLs were not fetched. Spot-check them before showing. Freedom Trail coordinates are approximate.
- The doctor attribution check fails because of #23 until the humans decide.
- Auth is dev mode only (the bearer token is the user id). There is no real session issuer yet.
- Analytics and recommendations use seed data for 6 users. The demo needs rider events that are consistent across services (game-engine points vs our analytics).

## How to resume
1. Delete the stop file: `Remove-Item insights-sponsors/.work/STOP` (also `data-platform/.work/STOP` if that pair should run).
2. From the repo root: `node scripts/duo.mjs insights-sponsors planner` and `node scripts/duo.mjs insights-sponsors builder` (or VS Code task "Duo up: eren").
3. Say `start` to the planner and `go` to the builder.
4. First thing for the builder: `git merge wip/insights-sponsors-014` (commit ed294ec) on main, run `python -m pytest -q` (expect 149 passed), then continue 014 at Step 1 (`repo/ids.py`) using its "Resume notes".
5. First thing for the planner: check #26, #23 and #5 (rank-4), and confirm the home_line column name with data-platform.

## Update (merge and cleanup pass)
- Rank mismatch: game-engine now has 8 named ranks in the shared `ranks` table; our `/rank-tiers` still lists 5 placeholder tiers and offers use `min_rank` 1-5 (OpenAPI caps min_rank at 5). Align before the demo.

- Rank migration done (v0.6.0): `/rank-tiers` reads game-engine's 8 named ranks from the shared `ranks` table (memory mode copy in `ranks.py`), `min_rank` max is 8, demo offer percentages follow the tier table (placeholders), the free-item demo offer is at rank 8. This supersedes the "Rank mismatch" note above.

## Update (final checks)
- Added `node scripts/demo.mjs` and docs/DEMO.md. Fixed: blank-title content rows (365 removed; the source was later dropped), 500s on malformed ids in Postgres mode, setup-me.mjs syntax error (#39). 198 insights-sponsors tests, 130 data-platform tests, 58 node tests pass.

## Update (issues #43/#44, sources)
- data-platform: `GET /me/travel` (routes/travel.py, tests/test_travel.py), migration 0012 (nearby_spots.fun_fact, fact_faves). insights-sponsors v0.7.0: /me/faves, Spot.fun_fact, stop-facts fallback. Historic-inventory source dropped (code and rows removed); ingestion User-Agent T-Quest-Hackathon/1.0. #43 and #44 stay open (unlocked_spots writer in game-engine, #64; along-line ordering). Counts: docs/DATA_SOURCES.md.

## Update (public-demo work, merged to main)
- Added shared/ (signed-token auth, hardening), demo login on insights (POST /auth/demo-login), scripts/seed-demo-db.mjs (+ data_platform.seed_demo), Dockerfiles (untested), web/ app, docs/DEPLOY.md, docs/APP_SCOPE.md, scripts/e2e-prod.mjs (47/47). Migrations 0013 (rank names) and 0014 (all sponsors demo). Deployment is manual: docs/DEPLOY.md. Not verified: Docker builds, hosts, Vercel, seed script against a real second DB.

## Update (local-demo pass)
- The demo runs locally: `node scripts/demo-up.mjs`, checks with `node scripts/preflight.mjs`, runbook docs/DEMO.md. Public hosting is future work (docs/FUTURE_PUBLIC_HOSTING.md, future-hosting/). PostgresRepository._q now reuses one connection per worker thread. Faves rows carry is_demo (migration 0015) and are removed by scripts/reset-demo.mjs.
