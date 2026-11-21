# HANDOFF: data-platform (builder session)

## Status
The builder finished prompts 001 to 014 and stopped safely before 015. All code is on main. Nothing has ever run against a real database: this machine has no Docker or Postgres and there is no Tiger Cloud URL or MBTA key (issue #25). Everything verified so far is DB-free: 59 tests pass, 50 DB tests skip.

## Done (prompt ids)
- 001 Scaffold: `pyproject.toml`, `docker-compose.yml` (timescaledb pg16), `.env.example`, `migrate.py` (ordered, idempotent, `-- migrate:no-transaction` files split into statements), `app.py`, `db.py`, README.
- 002 `migrations/0001_core.sql`: routes, stops, route_stops, stop_facts, users, consent, friends, ranks, `rider_events` and `points_ledger` hypertables, append-only ledger trigger, `user_points`, `user_rank`; `seeds/dev_seed.sql`, `python -m data_platform.seed`.
- 003 `0002_rewards.sql`: sponsors, stores, offers, rewards, badges, quests, physical_rewards, store_inventory, user_collections, redemptions, `expire_redemptions()`.
- 004 `contracts-draft/` (SCHEMA.md, schema.sql, api/data-platform.yaml, PUBLISH.md) for Eren to copy into `../contracts/`.
- 005 `0003_realtime.sql`: vehicles and predictions hypertables, compression, retention, alerts, alert_entities, `active_alerts`; `bench.compression_stats()`.
- 006 `0004_aggregates.sql`: `leaderboard_daily`, `leaderboard()`, `home_line_weekly`, `home_line`, `users_affected_by_alert()`, `personal_stats_daily`, `user_stop_visits`. Also fixed a bug in the 001 runner (no-transaction files must be split per statement).
- 007 `mbta.py`, `load_static.py`, `ingest.py`, recorded fixtures in `tests/fixtures/mbta/`.
- 008 Read API (all 8 paths) in `src/data_platform/routes/`, pydantic `models.py`, contract tests against the OpenAPI draft.
- 009 `bench.py` (`python -m data_platform.bench`, `--cleanup`): compression ratio and CAGG vs raw latency; writes `bench/RESULTS.md` (not yet produced).
- 010 `0005_schema_v01.sql`: insights-sponsors additions (#22), `user_rank` includes every user; `concat_schema.py` rebuilds `contracts-draft/db/schema.sql`.
- 011 Compression orderby now includes the unique-index id column (edited 0003 in place).
- 012 `0006_insights_aggregates.sql`: `user_stop_daily`, `user_stop_hourly`, `stop_popularity_hourly`, `home_line.checkins_28d`.
- 013 `tests/test_sql_syntax.py`: every migration and seed parses with the real Postgres parser (pglast) and idempotency rules hold.
- 014 `verify.py` (`python -m data_platform.verify`): one-command run for when a DB exists; writes `verify/VERIFY.md` and `verify/verify.json`, redacted. Committed in the safe-stop commit.

## In progress / partial
Nothing half-done on main; no wip branch needed. Prompt 015 (Dockerfile and compose services) is `ready` and was not started.

## Remaining (priority order)
1. 015 containerize services (next).
2. 016 and 017: queued by the planner; read `.work/queue/`.
3. Human step: run `python -m data_platform.verify` against local docker or Tiger Cloud to close every DB-unverified item (002 to 012 plus the benchmark), then publish `contracts-draft/` to `../contracts/` per PUBLISH.md (regenerate schema.sql with a real pg_dump first).

## Blockers and open issues
- Issue #25: a human must provide a database (docker or Tiger Cloud free plan) and a free MBTA API key. Waiting on the human; blocks all DB verification and `bench/RESULTS.md`.
- Contract publication (`../contracts/db/`, `../contracts/api/data-platform.yaml`) is a human step by Eren; other agents are waiting for it.
- The attribution check fails on one old teammate commit (a Co-authored-by trailer). Fixing needs a history rewrite, which the builder must not do; the planner opened a humans issue.

## Decisions made and deviations
- Builder-made choices are in each `.work/reports/NNN.md` under Deviations. Main ones: concatenated `schema.sql` instead of pg_dump; `user_rank` is built from `users`; ledger cleanup in the benchmark briefly disables the append-only trigger; `/predictions` keeps rows by `coalesce(arrival_time, departure_time)`; synthetic benchmark data is generated server-side.
- Billing: nothing uses Anthropic keys or pay-per-usage (AGENTS.md Billing rule). `MBTA_API_KEY` is the free MBTA key only.

## Risks for the demo
- No migration has run on real TimescaleDB. Likeliest failures: FILTER clauses in continuous aggregates (needs 2.7+), compression with the unique indexes, DELETE on compressed chunks in `bench --cleanup`.
- Static MBTA load needs a key (about 340 requests); without a key the API returns 429.
- No compression ratio or latency numbers exist yet; the demo needs one real benchmark run.

## How to resume
1. Delete `.work/STOP`.
2. From the repo root: `node scripts/duo.mjs data-platform builder` (planner: `node scripts/duo.mjs data-platform planner`).
3. First thing: if a DB is available, run `python -m data_platform.verify` and attach `verify/VERIFY.md` to the next report; otherwise start prompt 015.
