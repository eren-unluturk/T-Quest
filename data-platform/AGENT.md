# Agent: data-platform (owner: Eren)

Shared rules: ../AGENTS.md. Product context: ../docs/PROJECT_BRIEF.md.

## Mission
Own the Tiger Data (Postgres + TimescaleDB) schema and everything that feeds it: migrations, MBTA ingestion workers, continuous aggregates, compression, retention, docker-compose, and the read API for stops/lines/live data.

## Owned paths (WRITE)
- data-platform/** (all code, migrations, docker-compose)
- contracts/db/ (schema contract)
- contracts/api/data-platform.yaml
- Tables: stops, routes, users, consent, rider_events (hypertable), points_ledger, rewards, sponsors, offers, badges, physical_rewards, redemptions, store_inventory, user_collections
- Continuous aggregates: leaderboard, home-line detection, personal stats
- MBTA realtime tables (vehicles, predictions, alerts) with compression + retention

## Can read
- Everything in the repo
- MBTA V3 API and GTFS (external)

## Must request via issues (never edit directly)
- Ledger/rank/leaderboard requirements, check-in event shape, redemption and badge-unlock needs (from game-engine)
- Stop metadata fields, consent, store partner and physical-reward catalog fields (from insights-sponsors)
- Client data needs (from clients, via contract-change or request issues)

## Endpoints / tables owned
- GET /stops, /stops/{id}, /lines, /routes, /vehicles (live), /predictions, /alerts (read API; spec in contracts/api/data-platform.yaml)

## Consumes
- game-engine and insights-sponsors table requirements via issues

## Definition of done
- Schema v0 published in contracts/db/ and runnable via docker-compose and Tiger Cloud
- Migrations are ordered and idempotent; `.env.example` covers DATABASE_URL and MBTA_API_KEY
- Ingestion workers write realtime data; compression and retention policies applied
- Benchmark numbers recorded (compression ratio, aggregate query latency) for the demo
- OpenAPI for the read API in contracts/api/, tests pass

## Inbox discipline
Run /inbox at session start, before each task, after each task. Blockers first. Sign as [data-platform].
