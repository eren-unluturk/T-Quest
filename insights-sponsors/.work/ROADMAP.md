# ROADMAP: insights-sponsors

## Risks and cross-agent dependencies
- **Contract promotion is a human step.** Builders cannot write `contracts/`. After 002 is done, Eren copies `insights-sponsors/openapi/insights-sponsors.yaml` to `contracts/api/insights-sponsors.yaml` (allowed for eren by D13) and commits it. #8 (client-bryan) waits on this.
- **Tiger Data schema (#1, data-platform) not published yet.** 007 (Postgres backend) is blocked on it. Everything before it runs on the in-memory backend with seed JSON. Our column and aggregate needs went to data-platform as #22.
- **History attribution:** commit 6732e8d (squash merge of PR #19) carries a co-author trailer, so doctor fails. A human decision is needed (#23). Agents do not rewrite history.
- **Redemption split with game-engine (#5).** Game-engine owns `POST /redemptions` and `/redemptions/verify` (contracts/api/game-engine.yaml). We own the offer and physical-reward catalog and the eligibility rule (`min_rank`, `required_badge_id`). Rank discount numbers come from game-engine `x-rules.ranks`. Rank 1 is 3% there against "~5%" in the brief; flagged on #5.
- **Badge ids** for physical rewards are owned by game-engine. Our seed uses placeholder ids (003), to be reconciled on #5.
- **Port clash:** game-engine.yaml `servers` uses `localhost:8002`, but `.env.example` gives 8002 to insights-sponsors and 8003 to game-engine. Flagged on #5.
- **Auth:** dev mode treats the bearer token as the user id until a session issuer is agreed (#8).
- Kickoff (#11) is a human task: Eren fills the GitHub handle in TEAM.md and team.json and runs setup-me.

## Phase 1: service and contract
- [ ] 001 Scaffold FastAPI service (queue/001-scaffold-service.md)
- [ ] 002 Draft OpenAPI v0 (queue/002-openapi-draft.md, #8)
- [ ] HUMAN: promote the OpenAPI draft to contracts/api/insights-sponsors.yaml (#8)

## Phase 2: catalog, content, consent (in-memory)
- [ ] 003 Models, repository, seed content (queue/003-models-memory-repo-seed.md)
- [ ] 004 Content and catalog endpoints (queue/004-content-catalog-endpoints.md, #5)
- [ ] 005 Consent endpoints and guard (queue/005-consent-endpoints-and-guard.md)

## Phase 3: analytics and recommendations
- [ ] 006 Analytics and recs: SQL drafts plus in-memory (queue/006-analytics-recs-sql-draft.md, #3)
- [ ] 007 Postgres (Tiger Data) backend (queue/007-postgres-backend.md, #1) [blocked on schema]

## Later
- AI-assisted recommendation text (ANTHROPIC_API_KEY optional)
- Demo numbers: aggregate latency vs raw (with data-platform)
