# ROADMAP: insights-sponsors

## Risks and cross-agent dependencies
- **Contract promotion is a human step.** Builders cannot write `contracts/`. Draft is done (002, commit cf4e57b); Eren copies `insights-sponsors/openapi/insights-sponsors.yaml` to `contracts/api/insights-sponsors.yaml` (allowed for eren by D13) and commits it. Tracked in #26. #8 (client-bryan) waits on this.
- **Tiger Data schema (#1, data-platform):** a v0 draft exists in `data-platform/contracts-draft/db/` (migrations 0000-0004, not yet in contracts/). Our additions arrive in data-platform prompt 010 / migration 0005. Renames from the #22 ACK: store_partners->stores, physical_rewards.kind->item_type, store_inventory.quantity->stock, rank via the `user_rank` view, badges via `user_collections`, home line via `home_line_weekly` (checkins_28d). When 0005 lands, the planner writes a fresh ready prompt (014) that supersedes 007. It must handle text session ids vs uuid `user_id`, and `home_line_weekly` exposes `rides_28d` (checkin + ride_start). 007 (Postgres backend) is blocked on it. Everything before it runs on the in-memory backend with seed JSON. Our column and aggregate needs went to data-platform as #22.
- **History attribution:** commit 6732e8d (squash merge of PR #19) carries a co-author trailer, so doctor fails. A human decision is needed (#23). Agents do not rewrite history.
- **Redemption split with game-engine (#5).** Game-engine owns `POST /redemptions` and `/redemptions/verify` (contracts/api/game-engine.yaml). We own the offer and physical-reward catalog and the eligibility rule (`min_rank`, `required_badge_id`). Rank discount numbers come from game-engine `x-rules.ranks`. Rank 1 is 3% there against "~5%" in the brief; flagged on #5.
- **Badge ids** for physical rewards are owned by game-engine. Our seed uses placeholder ids (003), to be reconciled on #5.
- **Port clash:** game-engine.yaml `servers` uses `localhost:8002`, but `.env.example` gives 8002 to insights-sponsors and 8003 to game-engine. Flagged on #5.
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
- [ ] 007 Postgres (Tiger Data) backend (queue/007-postgres-backend.md, #1) [blocked on schema]

## Phase 4: hardening and AI
- [x] 008 Hardening and contract conformance test (queue/008-hardening-contract-conformance.md, #8) verified
- [-] 009 CANCELLED: AI reasons (AGENTS.md Billing: no API keys)
- [ ] 011 Document consent error responses in OpenAPI (queue/011-openapi-error-responses.md, #8)
- [ ] 012 Boston analytics GET /analytics/boston, k-anonymous (queue/012-boston-analytics.md, #3)
- [ ] 013 Consented place-visit ingest and delete-on-revoke (queue/013-place-visit-ingest.md)
- [ ] 010 Seed coverage (neighborhoods, bus) and MBTA API verification (queue/010-seed-coverage-and-verification.md)

## Later
- AI text for recommendations: future only (no API billing this hackathon)
- Demo numbers: aggregate latency vs raw (with data-platform)

## Review notes
- 001 verified: 6 tests pass, /health on :8002. Nit for a later hardening prompt: `config.py` reads `../.env` relative to cwd; resolve it from the package path instead.
- 002 verified: 10 tests pass, the spec validates, and every path and field matches the prompt. Accepted deviations: shared components, a recs limit max of 50, extra 404/422 responses. Draft announced on #8 and #5.
- 003 verified: 22 tests pass, a model/OpenAPI field-parity test, referential integrity, no real brands. Sampled fun facts read as accurate. Gaps: coordinates approximate, URLs unchecked, 5 of 13 stops Downtown, no bus stops, so follow-up 010. The consent default-rows question is already answered by 005 step 1. Badge ids posted on #5.
- 004 verified: 41 tests pass; facts, trail, fun-facts (no auth), local picks, offers filters and eligibility, catalog, shape checks against OpenAPI. 008 now reuses tests/openapi_shape.py instead of jsonschema. Eligibility rule posted on #5.
- 005 verified: 52 tests pass; single gate has_consent, require_consent 401/403/200, policy 409, idempotent revoke. Undocumented 409/403 led to 011 (draft not promoted yet, so it can still change). #26 updated.
- 006 verified: 76 tests pass, hand-checked user-1 numbers, consent gate proven by spy and source scan, sponsorship order-neutral, 4 parameterized SQL files. 009 cancelled by the billing rule. Added 012 (Boston analytics) and 013 (place-visit ingest).
- 008 verified: 100 passed, 1 intentional skip; every YAML operation validated against the live app; no extra routes; .env resolved from the package path. Later spec changes (011-013) are covered automatically.
