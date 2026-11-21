# HANDOFF: data-platform (planner + builder), safe stop 2026-11-21 13:20

## Status
Prompts 001-014 are built and committed. The planner verified 004, 011, 013 and 014. Everything else is built and reviewed but has never run against a database, because this machine has no Docker or Postgres (#25). The schema (migrations 0000-0006), MBTA loader/worker, read API, benchmark and contract drafts exist. Contract drafts are ready in `data-platform/contracts-draft/` but are not published to `contracts/` (#27, human step), so game-engine and insights-sponsors are still blocked on the schema. Prompts 015 and 016 are queued and ready; none is in progress. The builder finished 014 at stop time; no wip branch exists. DB-free test status: 59 passed, 50 skipped.

## Done (built; [V] = verified by planner, others DB-unverified)
- 001 scaffold: `pyproject.toml`, `docker-compose.yml` (timescaledb pg16), `.env.example`, `migrations/0000_extensions.sql`, `src/data_platform/{app,db,migrate}.py` (ordered, idempotent runner with `-- migrate:no-transaction`), `GET /health`.
- 002 `migrations/0001_core.sql`: routes, stops, route_stops, stop_facts, users, consent (pk user_id+scope), friends, ranks (seeded), `rider_events` and `points_ledger` hypertables, append-only ledger trigger, views user_points, user_rank, active_consent; `seeds/dev_seed.sql`, `python -m data_platform.seed`.
- 003 `migrations/0002_rewards.sql`: sponsors, stores, offers, rewards, badges, quests, physical_rewards, store_inventory, user_collections, redemptions, `expire_redemptions()`.
- 004 [V] `contracts-draft/db/SCHEMA.md`, `schema.sql` (concatenation), `contracts-draft/api/data-platform.yaml`, `contracts-draft/PUBLISH.md`.
- 005 + 011 [V for 011] `migrations/0003_realtime.sql`: vehicles and predictions hypertables (compression orderby includes ids, 1-day compress, 30-day retention), alerts, alert_entities, active_alerts.
- 006 `migrations/0004_aggregates.sql`: leaderboard_daily CAGG + `leaderboard()`, home_line_weekly + home_line, `users_affected_by_alert()`, personal_stats_daily, user_stop_visits.
- 007 `src/data_platform/{mbta,load_static,ingest}.py` with fixtures; parse and mocked-transport tests pass.
- 008 read API: GET /health, /routes, /lines, /stops, /stops/{id}, /vehicles, /predictions, /alerts (`src/data_platform/routes/`), contract tests.
- 009 `python -m data_platform.bench` (synthetic data, compression ratio, CAGG vs raw latency, cleanup). No numbers yet.
- 010 `migrations/0005_schema_v01.sql`: #22 additions (stops.mode, freedom_trail_sites, fun_facts, place_visits hypertable with 90-day retention, offer columns, consent.granted), user_rank covers all users.
- 012 `migrations/0006_insights_aggregates.sql`: user_stop_daily, user_stop_hourly CAGGs, stop_popularity_hourly view (home_line part superseded by 016).
- 013 [V] `tests/test_sql_syntax.py`: every migration and seed parses with pglast; idempotency checks.
- 014 [V] `src/data_platform/verify.py` (`python -m data_platform.verify`): migrate twice, seed, MBTA load + one ingest, pytest, small bench + cleanup, TimescaleDB introspection; writes redacted `verify/VERIFY.md` and `verify/verify.json` (gitignored); exits non-zero on any failed step.

## In progress / partial
- Nothing in progress. No wip branch.
- Partial by design: home_line still uses 28 days and `checkins_28d`. Prompt 016 fixes it (30 days, tie to most recent, `checkins_30d`), and #4 and #22 were already told the new name.

## Remaining (priority order)
1. 016 home_line 30-day rule (correct contracts for game-engine and insights-sponsors). The builder picks by number, so 015 runs first.
2. 015 Dockerfile + compose services (api on 8001, migrate, ingest).
3. HUMAN #27: publish contracts-draft/ into contracts/ (after 016; regenerate schema.sql with a real pg_dump if a DB exists). This blocks game-engine and insights-sponsors.
4. HUMAN #25: database + MBTA key, then `python -m data_platform.verify`; planner then ticks 001-003, 005-010, 012.
5. Later: align rider_events with game-engine's contracts/events check-in schema once proposed.
Next queue prompts: 015, 016 (only two remain; the planner should queue more on resume).

## Blockers and open issues
- #25 (to:humans, blocker; Eren): no database and no MBTA_API_KEY on this machine. Blocks all DB verification and benchmark numbers.
- #27 (to:humans; Eren): publish contracts-draft/ into contracts/. Blocks game-engine and insights-sponsors from using real tables.
- #24 (to:humans; Eren and team): commit 6732e8d has a Co-authored-by trailer; needs a coordinated history rewrite and force-push. Makes `check-attribution` fail.
- #1 (ours), #4 (game-engine), #6 and #22 (insights-sponsors), #8 (client-bryan): acked; close after #27 publication with `node ../scripts/done.mjs <n> --note "..."`.
- #11 (humans kickoff): acked; GitHub handle in TEAM.md is Eren's to fill.

## Decisions made and deviations from plan
- Contracts are staged in `data-platform/contracts-draft/` because neither agent may write `contracts/`.
- Read API endpoints are public (no auth, no user data). Port 8001 planned in 015.
- Consent follows insights-sponsors' model: pk (user_id, scope), update in place, `policy_version`, generated `granted`.
- Write ownership: game-engine writes users, badges, ranks, rider_events, points_ledger, user_collections, redemptions, friends; insights-sponsors writes content, catalog, consent, place_visits; data-platform writes routes, stops, route_stops and realtime tables.
- home_line mirrors game-engine `delay.py` (016). Names given to insights-sponsors: stores (not store_partners), item_type, stock, checkins_30d.
- 0003 was edited in place (011) since no DB had applied it.
- No per-token or Anthropic API usage anywhere (Billing rule).
- Builder twice built from an older version of an amended prompt (006, 012). Amend prompts only while they are still unstarted, or write a follow-up.

## Risks for the demo/pitch
- No SQL has run on Postgres/TimescaleDB yet. TimescaleDB-specific failures (FILTER in CAGGs, compression with unique indexes, policies) may appear on first run. Run verify early.
- No compression ratio or latency numbers yet; they are the Tiger Data prize angle.
- Without an MBTA key the static load cannot finish (about 20 req/min public limit).
- Other agents are still on fake data until #27 is published.
- Attribution history failure (#24) could look bad if judges inspect history.
- Builder notes: `bench --cleanup` deletes from compressed chunks (needs TimescaleDB 2.11+); the static MBTA load is about 340 requests.

## How to resume
1. Delete `data-platform/.work/STOP`.
2. From the repo root: `node scripts/duo.mjs data-platform planner` and `node scripts/duo.mjs data-platform builder` (or the VS Code tasks).
3. First thing: the planner runs `node ../scripts/inbox.mjs`, checks #25/#27 for human progress, then queues new prompts (only 015 and 016 remain). If a DB now exists, have Eren run `python -m data_platform.verify` and review `verify/VERIFY.md`.
