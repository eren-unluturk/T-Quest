# ROADMAP: data-platform

## Risks and cross-agent dependencies
- **Contract publication is a human step.** The builder may not write `../contracts/`; the planner may not write outside `.work/`. Prompt 004 stages drafts in `data-platform/contracts-draft/`; Eren copies them per `contracts-draft/PUBLISH.md` (his D13 paths allow it without ALLOW_SHARED). #1 and #8 cannot close until that happens.
- **insights-sponsors 007 (Postgres backend) and 005 (consent) are blocked on our schema (#1).** Consent table in 002 matches their model: pk (user_id, scope), scopes `location`/`place_visits`, `policy_version`, re-grant updates in place.
- **game-engine** has in-memory ledger/redemption rules (`game-engine/src/game_engine/`) and will propose a check-in event JSON Schema in `contracts/events/`. `rider_events` columns in 002 follow CheckinRequest; adjust when their schema lands.
- game-engine needs "vehicle seen at stop within 300 s": served by `/vehicles?stop_id=&since_s=` (008) on `vehicles` (005).
- Attribution check fails on history commit 6732e8d (a teammate's Co-authored-by trailer, merged via PR #19). Fix requires a history rewrite + force-push, which agents may not do. Raised to humans.
- MBTA_API_KEY needed for live ingestion (007); prompt falls back to fixtures.

## Phase 1: schema v0 and contracts (unblocks game-engine, insights-sponsors, clients)
- [ ] 001 Scaffold service, docker-compose, env, migration runner (queue/001-scaffold-compose-migrations.md, #1)
- [ ] 002 Core schema: transit, users, consent, friends, rider_events, points_ledger, ranks (queue/002-core-schema.md, #4, #6)
- [ ] 003 Rewards schema: sponsors, stores, offers, rewards, quests, badges, physical rewards, redemptions (queue/003-rewards-schema.md, #4, #6)
- [ ] 004 Schema contract doc + data-platform OpenAPI drafts (queue/004-contract-drafts.md, #1, #8)
- [ ] HUMAN: Eren publishes contracts-draft/ into contracts/ (then planner closes #1, #4, #6 and replies on #8)

## Phase 2: Tiger Data features
- [ ] 005 MBTA realtime tables with compression and retention (queue/005-realtime-tables.md)
- [ ] 006 Continuous aggregates: leaderboard, home line, personal stats (queue/006-continuous-aggregates.md, #4)
- [ ] 007 MBTA static loader and realtime ingestion worker (queue/007-mbta-ingestion.md)
- [ ] 008 Read API implementation (queue/008-read-api.md, #8)
- [ ] 009 Demo benchmark: compression ratio and aggregate latency (queue/009-benchmarks.md)

## Later (not yet queued)
- Tiger Cloud deployment run and verification of all migrations there
- Align rider_events with game-engine's contracts/events check-in schema
