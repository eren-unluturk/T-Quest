# ROADMAP: data-platform

Status legend: [x] verified by planner. [ ] with "built, DB-unverified" = code done and reviewed, waiting for a live DB run (#25). [ ] "not started" = queued, ready.
SAFE STOP 2026-11-21 13:17. See HANDOFF.md.

## Risks and cross-agent dependencies
- **Billing rule (AGENTS.md "Billing", 2026-11-21): no API-key / per-token billing this hackathon.** Nothing in data-platform may add, read or depend on ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN. No LLM features get queued. Recommendations and aggregates stay deterministic SQL. Audit on 2026-11-21: data-platform code, config and .env.example have no Anthropic dependency; insights-sponsors 009 (LLM recommendation reasons) is cancelled by its planner.
- **No database on this machine (#25, to:humans, blocker).** Docker and Postgres are absent; no migration has ever run against Postgres. Syntax is proven by pglast (013); semantics are not. MBTA_API_KEY also needed (asked on #25).
- **Contract publication is a human step (#27).** Drafts live in `data-platform/contracts-draft/`; Eren copies them per `contracts-draft/PUBLISH.md`. Publish after 016 so contracts carry `checkins_30d`. #1, #4, #6, #8, #22 close after publication.
- **game-engine and insights-sponsors are blocked on publication.** game-engine (PRs #28-#30) still runs on in-memory fake data. insights-sponsors' Postgres backend waits on contracts/db.
- Home line rule is owned by game-engine `delay.py` (30 days, min 5, tie to most recent); our view still uses 28 days until 016 lands. #4 and #22 were told `checkins_30d`.
- game-engine needs "vehicle seen at stop within 300 s": served by `/vehicles?stop_id=&since_s=` (008) on `vehicles` (005).
- Attribution check fails on history commit 6732e8d (teammate Co-authored-by trailer via PR #19). Needs a human history rewrite + force-push (#24).

## Phase 1: schema v0 and contracts
- [ ] 001 Scaffold service, docker-compose, env, migration runner (queue/001-scaffold-compose-migrations.md, #1) -- built, DB-unverified
- [ ] 002 Core schema: transit, users, consent, friends, rider_events, points_ledger, ranks (queue/002-core-schema.md, #4, #6) -- built, DB-unverified
- [ ] 003 Rewards schema: sponsors, stores, offers, rewards, quests, badges, physical rewards, redemptions (queue/003-rewards-schema.md, #4, #6) -- built, DB-unverified
- [x] 004 Schema contract doc + data-platform OpenAPI drafts (queue/004-contract-drafts.md, #1, #8) -- verified (schema.sql is a concatenation until a DB exists)
- [ ] HUMAN: Eren publishes contracts-draft/ into contracts/ (#27) -- blocked on human

## Phase 2: Tiger Data features
- [ ] 005 MBTA realtime tables with compression and retention (queue/005-realtime-tables.md) -- built, DB-unverified (compression bug fixed by 011)
- [ ] 006 Continuous aggregates: leaderboard, home line, personal stats (queue/006-continuous-aggregates.md, #4) -- built, DB-unverified
- [ ] 007 MBTA static loader and realtime ingestion worker (queue/007-mbta-ingestion.md) -- built, DB-unverified; live load needs MBTA_API_KEY (#25)
- [ ] 008 Read API implementation (queue/008-read-api.md, #8) -- built, DB-unverified (paths/params match spec)
- [ ] 009 Demo benchmark: compression ratio and aggregate latency (queue/009-benchmarks.md) -- built, no numbers until a DB run (#25)
- [ ] 010 Schema v0.1: insights-sponsors additions + user_rank for all users (queue/010-schema-v01-insights.md, #22) -- built, DB-unverified
- [x] 011 Fix compression settings vs unique indexes (queue/011-fix-compression-unique.md) -- verified (text test; live compression pending #25)
- [ ] 012 Insights aggregates (user_stop_daily, stop_popularity_hourly) (queue/012-insights-aggregates.md, #22) -- built, DB-unverified; home_line part superseded by 016
- [x] 013 DB-free SQL syntax check with pglast (queue/013-sql-syntax-check.md) -- verified
- [x] 014 One-command verification run (queue/014-verify-command.md, #25) -- verified (DB-free tests pass; no-DB run reports cleanly)
- [ ] 015 Dockerfile + compose services for API and ingestion (queue/015-containerize-services.md) -- not started (ready, next)
- [ ] 016 home_line 30-day rule + checkins_30d, matching game-engine delay.py (queue/016-home-line-30d.md, #4, #22) -- not started (ready)
- [ ] HUMAN: Eren publishes v0.1 contracts-draft/ (#27), then planner closes #22

## Later (not yet queued)
- FUTURE, out of scope now: any per-token LLM feature (for example AI-written recommendation reasons). Not to be queued during the hackathon.
- Tiger Cloud deployment run and verification of all migrations there (covered by 014 once a URL exists)
- Align rider_events with game-engine's contracts/events check-in schema (not proposed yet)
