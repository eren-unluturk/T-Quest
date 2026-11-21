# ROADMAP: data-platform

## Risks and cross-agent dependencies
- **Billing rule (AGENTS.md "Billing", 2026-11-21): no API-key / per-token billing this hackathon.** Nothing in data-platform may add, read or depend on ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN. No LLM features get queued. Recommendations and aggregates stay deterministic SQL. Audit on 2026-11-21: data-platform code, config and .env.example have no Anthropic dependency; insights-sponsors 009 (LLM recommendation reasons) is cancelled by its planner.
- **Contract publication is a human step.** The builder may not write `../contracts/`; the planner may not write outside `.work/`. Prompt 004 stages drafts in `data-platform/contracts-draft/`; Eren copies them per `contracts-draft/PUBLISH.md` (his D13 paths allow it without ALLOW_SHARED). #1 and #8 cannot close until that happens.
- insights-sponsors #22 asked for more tables (freedom_trail_sites, fun_facts, place_visits, extra offer columns). 006 now adds user_stop_daily / stop_popularity_hourly; 010 adds the rest. Name mapping posted on #22.
- **insights-sponsors 007 (Postgres backend) and 005 (consent) are blocked on our schema (#1).** Consent table in 002 matches their model: pk (user_id, scope), scopes `location`/`place_visits`, `policy_version`, re-grant updates in place.
- **game-engine** has in-memory ledger/redemption rules (`game-engine/src/game_engine/`) and will propose a check-in event JSON Schema in `contracts/events/`. `rider_events` columns in 002 follow CheckinRequest; adjust when their schema lands.
- game-engine needs "vehicle seen at stop within 300 s": served by `/vehicles?stop_id=&since_s=` (008) on `vehicles` (005).
- Attribution check fails on history commit 6732e8d (a teammate's Co-authored-by trailer, merged via PR #19). Fix requires a history rewrite + force-push, which agents may not do. Raised to humans.
- **No database on this machine (#25, to:humans).** Docker and Postgres are absent; all DB acceptance checks are deferred until a Tiger Cloud DATABASE_URL or Docker is available. Items are ticked only after a DB run.
- MBTA_API_KEY needed for live ingestion (007); requested on #25. Without a key the API allows ~20 req/min.
- Once a DB exists: Eren runs `python -m data_platform.verify` (014); planner reviews verify/VERIFY.md and ticks 001-003, 005-012.
- game-engine (PRs #28-#30) still uses in-memory fake data; it switches to our tables after publication (#27). Home line rule owned by game-engine delay.py; our view mirrors it (012).

## Phase 1: schema v0 and contracts (unblocks game-engine, insights-sponsors, clients)
- [ ] 001 Scaffold service, docker-compose, env, migration runner (queue/001-scaffold-compose-migrations.md, #1) -- reviewed: code OK, DB criteria unverified (no DB, #25)
- [ ] 002 Core schema: transit, users, consent, friends, rider_events, points_ledger, ranks (queue/002-core-schema.md, #4, #6) -- reviewed: OK, DB unverified; user_rank zero-point gap fixed in 010
- [ ] 003 Rewards schema: sponsors, stores, offers, rewards, quests, badges, physical rewards, redemptions (queue/003-rewards-schema.md, #4, #6) -- reviewed: OK, DB unverified
- [x] 004 Schema contract doc + data-platform OpenAPI drafts (queue/004-contract-drafts.md, #1, #8) -- verified (schema.sql is a concatenation until a DB exists)
- [ ] HUMAN: Eren publishes contracts-draft/ into contracts/ (#27; then planner closes #1, #4, #6 and replies on #8)

## Phase 2: Tiger Data features
- [ ] 005 MBTA realtime tables with compression and retention (queue/005-realtime-tables.md) -- reviewed: compression orderby conflicts with unique indexes, fix in 011; DB unverified
- [x] 011 Fix compression settings vs unique indexes (queue/011-fix-compression-unique.md) -- verified (text test passes; live compression still pending #25)
- [ ] 012 Insights aggregates + home_line aligned with game-engine delay.py, checkins_30d (queue/012-insights-aggregates.md, #22, #4) -- reviewed: aggregates OK; home_line built from pre-amendment text (28d) -> 016
- [x] 013 DB-free SQL syntax check with the real Postgres parser (queue/013-sql-syntax-check.md) -- verified: all migrations/seeds parse; 1 idempotency fix
- [ ] 014 One-command verification run for when a DB exists (queue/014-verify-command.md, #25)
- [ ] 015 Dockerfile + compose services for API and ingestion (queue/015-containerize-services.md)
- [ ] 016 home_line 30-day rule + checkins_30d, matching game-engine delay.py (queue/016-home-line-30d.md, #4, #22)
- [ ] 006 Continuous aggregates: leaderboard, home line, personal stats (queue/006-continuous-aggregates.md, #4) -- reviewed: OK (runner no-transaction fix good), DB unverified; missed the #22 amendment -> 012
- [ ] 007 MBTA static loader and realtime ingestion worker (queue/007-mbta-ingestion.md) -- reviewed: OK (parse/mock tests pass); live load needs MBTA_API_KEY + DB (#25)
- [ ] 008 Read API implementation (queue/008-read-api.md, #8) -- reviewed: OK (paths/params match spec; SQL DB-unverified). OpenAPI draft tweaked (limit/since_s defaults), so publish the current draft (#27)
- [ ] 009 Demo benchmark: compression ratio and aggregate latency (queue/009-benchmarks.md) -- reviewed: code OK; no numbers until a DB run (#25)
- [ ] 010 Schema v0.1: insights-sponsors additions + user_rank for all users (queue/010-schema-v01-insights.md, #22) -- reviewed: OK (SCHEMA.md now covers 0000-0005), DB unverified
- [ ] HUMAN: Eren publishes v0.1 contracts-draft/ (then planner closes #22)

## Later (not yet queued)
- FUTURE, out of scope now: any per-token LLM feature (for example AI-written recommendation reasons). Not to be queued during the hackathon.
- Tiger Cloud deployment run and verification of all migrations there
- Align rider_events with game-engine's contracts/events check-in schema
