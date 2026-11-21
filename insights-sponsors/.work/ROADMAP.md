# ROADMAP: insights-sponsors

## Scope rule: no pay-per-usage this hackathon
Nothing we build may depend on usage-based billing: no LLM API keys or per-token calls, no paid Tiger Cloud tier (local docker TimescaleDB or the Tiger Cloud Free plan only), no paid map or geocoding APIs. The MBTA V3 key is free and optional. Every prompt must stay within this; deferred items are listed under "Out of scope: do later".

## Risks and cross-agent dependencies
- **Contract promotion is a human step.** Builders cannot write `contracts/`. Draft is done (002, commit cf4e57b); Eren copies `insights-sponsors/openapi/insights-sponsors.yaml` to `contracts/api/insights-sponsors.yaml` (allowed for eren by D13) and commits it. Tracked in #26. #8 (client-bryan) waits on this.
- **Tiger Data schema (#1, data-platform):** a v0 draft exists in `data-platform/contracts-draft/db/` (migrations 0000-0004, not yet in contracts/). Our additions arrive in data-platform prompt 010 / migration 0005. Renames from the #22 ACK: store_partners->stores, physical_rewards.kind->item_type, store_inventory.quantity->stock, rank via the `user_rank` view, badges via `user_collections`, home line via `home_line_weekly` (checkins_28d). When 0005 lands, the planner writes a fresh ready prompt (014) that supersedes 007. It must handle text session ids vs uuid `user_id`, and `home_line_weekly` exposes `rides_28d` (checkin + ride_start). 007 (Postgres backend) is blocked on it. Everything before it runs on the in-memory backend with seed JSON. Our column and aggregate needs went to data-platform as #22.
- **History attribution:** commit 6732e8d (squash merge of PR #19) carries a co-author trailer, so doctor fails. A human decision is needed (#23). Agents do not rewrite history.
- **Redemption split with game-engine (#5).** Game-engine owns `POST /redemptions` and `/redemptions/verify` (contracts/api/game-engine.yaml). We own the offer and physical-reward catalog and the eligibility rule (`min_rank`, `required_badge_id`). Rank discount numbers come from game-engine `x-rules.ranks`. AGREED on #5: game-engine keeps rank discounts at 3/5/7/10/12% (rank 1 is 3%, on purpose).
- **Badge ids:** game-engine adopted the shared slugs (PR #31): line-<route>-complete, freedom-trail, rank-3, rank-5. **rank-4 has no badge in game-engine**, but our seed has a rank-4 patch; decide whether to drop it or ask for one. 014 renames our seed to these slugs.
- **home_line column name conflict:** data-platform's #22 comment says `checkins_30d` (30-day window), but migration 0006 (their report 012) creates `checkins_28d`. Check the actual column before running 016.
- **Port clash:** RESOLVED; game-engine moved to 8003 (PR #28).
- **Auth:** dev mode treats the bearer token as the user id until a session issuer is agreed (#8).
- Kickoff (#11) is a human task: Eren fills the GitHub handle in TEAM.md and team.json and runs setup-me.

## Phase 1: service and contract
- [x] 001 Scaffold FastAPI service (queue/001-scaffold-service.md) verified
- [x] 002 Draft OpenAPI v0 (queue/002-openapi-draft.md, #8) verified
- [ ] HUMAN: promote the OpenAPI draft to contracts/api/insights-sponsors.yaml (#26, then close #8)

## Phase 2: catalog, content, consent (in-memory)
- [x] 003 Models, repository, seed content (queue/003-models-memory-repo-seed.md) verified
- [x] 004 Content and catalog endpoints (queue/004-content-catalog-endpoints.md, #5) verified
- [x] 005 Consent endpoints and guard (queue/005-consent-endpoints-and-guard.md) verified

## Phase 3: analytics and recommendations
- [x] 006 Analytics and recs: SQL drafts plus in-memory (queue/006-analytics-recs-sql-draft.md, #3) verified, #3 closed
- [-] 007 superseded by 014
- [x] 014 (partial, verified on live DB) Postgres backend: stops, offers, physical rewards, nearby spots, tourist content. Consent and place visits still memory (queue/014-postgres-catalog-content-consent.md, #1) IN PROGRESS at safe stop (see HANDOFF.md)
- [ ] 015 Bus parity in seed, analytics, recs (queue/015-bus-parity-seed.md) not started
- [ ] 016 Analytics, recs and Boston analytics on Postgres, plus latency bench (queue/016-postgres-analytics-recs.md, #1) not started
- [ ] 017 store_id validation and demo smoke script (queue/017-store-id-validation-demo-smoke.md) not started

## Phase 4: hardening and AI
- [x] 008 Hardening and contract conformance test (queue/008-hardening-contract-conformance.md, #8) verified
- [-] 009 CANCELLED: AI reasons (AGENTS.md Billing: no API keys)
- [x] 011 Document consent error responses in OpenAPI (queue/011-openapi-error-responses.md, #8) verified
- [x] 012 Boston analytics GET /analytics/boston, k-anonymous (queue/012-boston-analytics.md, #3) verified
- [x] 013 Consented place-visit ingest and delete-on-revoke (queue/013-place-visit-ingest.md) verified
- [x] 010 Seed coverage (neighborhoods, bus) and MBTA API verification (queue/010-seed-coverage-and-verification.md) verified

## Out of scope: do later (needs pay-per-usage, not this hackathon)
- 009 AI-written recommendation reasons (LLM API, per-token). Prompt kept as a cancelled reference.
- AI-generated or AI-ranked recommendations in general; recommendations stay deterministic SQL.
- Paid Tiger Cloud tiers or extra compute; the demo runs on local TimescaleDB or the Free plan.
- Paid geocoding or places APIs for matching place visits to stores.

## Later (free)
- Demo numbers: aggregate latency vs raw (with data-platform)

## Review notes
- 001 verified: 6 tests pass, /health on :8002. Nit for a later hardening prompt: `config.py` reads `../.env` relative to cwd; resolve it from the package path instead.
- 002 verified: 10 tests pass, the spec validates, and every path and field matches the prompt. Accepted deviations: shared components, a recs limit max of 50, extra 404/422 responses. Draft announced on #8 and #5.
- 003 verified: 22 tests pass, a model/OpenAPI field-parity test, referential integrity, no real brands. Sampled fun facts read as accurate. Gaps: coordinates approximate, URLs unchecked, 5 of 13 stops Downtown, no bus stops, so follow-up 010. The consent default-rows question is already answered by 005 step 1. Badge ids posted on #5.
- 004 verified: 41 tests pass; facts, trail, fun-facts (no auth), local picks, offers filters and eligibility, catalog, shape checks against OpenAPI. 008 now reuses tests/openapi_shape.py instead of jsonschema. Eligibility rule posted on #5.
- 005 verified: 52 tests pass; single gate has_consent, require_consent 401/403/200, policy 409, idempotent revoke. Undocumented 409/403 led to 011 (draft not promoted yet, so it can still change). #26 updated.
- 006 verified: 76 tests pass, hand-checked user-1 numbers, consent gate proven by spy and source scan, sponsorship order-neutral, 4 parameterized SQL files. 009 cancelled by the billing rule. Added 012 (Boston analytics) and 013 (place-visit ingest).
- 008 verified: 100 passed, 1 intentional skip; every YAML operation validated against the live app; no extra routes; .env resolved from the package path. Later spec changes (011-013) are covered automatically.
- 010 verified: 29 stops all match the MBTA API (verify_stops exit 0), 19 neighborhoods, 5 bus-mode stops, 103 passed. Bus stops have no events, so 015 follows up.
- 011 verified: 108 passed, spec 0.1.1 with PolicyMismatch 409 and ConsentRequired. #8 updated.
- 0005 landed (data-platform): ids are uuid for sponsors, stores, offers and physical_rewards, so 014 maps slugs with uuid5. Badge slugs follow `line-red-complete` (posted on #5). Our aggregates come in data-platform 012 (home_line becomes checkins_30d), so 016 comes later.
- data-platform 012 delivered migration 0006 (user_stop_daily, user_stop_hourly, stop_popularity_hourly, home_line.checkins_28d), not yet run against a DB. 016 queued and may be the first run.
- 012 verified: 123 passed; k-anonymity (3 riders) enforced on stops, days, totals and previous-period baselines; no ids in the body; spec 0.2.0; conformance covers 12 operations. Accepted the stricter privacy deviations.
- 013 verified: 149 passed; write never called without consent (spy plus source scan), revoke deletes visits, coordinates rounded, spec 0.3.0. store_id not validated (a 500 risk on uuid in postgres), so 017. 0.3.0 announced on #8 and #26.

## SAFE STOP 2026-11-21 13:17
Stopped on request. 014 in progress with the builder; 015-017 ready and not started. See HANDOFF.md.

## Update 2026-11-21 (unattended run)
- [x] 018 Nearby spots, categories, identity labels (migration 0010), demo sponsors, rank tiers, /offers rank and placement filters. Verified: 195 tests, 5 live-DB tests.
- [x] 019 Tourist content ingestion (migration 0011, `python -m ingest_content.run`), GET /stops/{id}/content, /loading-facts. Counts in docs/DATA_SOURCES.md.
- [x] 020 contracts/api/insights-sponsors.yaml published (v0.5.0), #26 delivered.
- [ ] Analytics, recommendations, consent and place visits on Postgres (015/016/017 unchanged, not started)
