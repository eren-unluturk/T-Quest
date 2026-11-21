---
id: 001
title: Scaffold Python service, docker-compose, env, and migration runner
status: done
issue: 1
depends_on: []
---
## Goal
A runnable data-platform skeleton: local TimescaleDB via docker-compose, `.env.example`, a Python 3.11 FastAPI package with a health route, and an ordered, idempotent SQL migration runner that works against local docker and Tiger Cloud.

## Context
- `../AGENTS.md`, `AGENT.md`, `../DECISIONS.md` (D1, D2, D10, D12)
- `README.md` (this folder; currently a stub)
- Existing empty dirs: `src/`, `tests/`

## Steps
1. `pyproject.toml` (package `data_platform` under `src/`, Python >= 3.11). Dependencies: fastapi, uvicorn[standard], psycopg[binary] (v3), httpx, python-dotenv. Dev: pytest, pytest-asyncio.
2. `docker-compose.yml` in `data-platform/`: one service `db` using image `timescale/timescaledb:latest-pg16`, port 5432, named volume, `POSTGRES_PASSWORD`/`POSTGRES_DB=tquest` from `.env`, healthcheck with `pg_isready`.
3. `.env.example` in `data-platform/` with: `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tquest`, `POSTGRES_PASSWORD=postgres`, `MBTA_API_KEY=`, `MBTA_API_BASE=https://api-v3.mbta.com`, and a commented Tiger Cloud example `DATABASE_URL=postgres://tsdbadmin:<password>@<host>:<port>/tsdb?sslmode=require`. Confirm `.env` is gitignored (root or local `.gitignore`; add a local `data-platform/.gitignore` if needed).
4. `migrations/` folder with `0000_extensions.sql`: `CREATE EXTENSION IF NOT EXISTS timescaledb;` and `CREATE EXTENSION IF NOT EXISTS pgcrypto;` (for `gen_random_uuid()`).
5. `src/data_platform/migrate.py` (runnable as `python -m data_platform.migrate`): reads `DATABASE_URL`, creates `schema_migrations(version text primary key, applied_at timestamptz default now(), checksum text)`, applies `migrations/NNNN_*.sql` files in lexical order, each in its own transaction, skipping applied versions; warns (does not fail) if a checksum changed. Note: `add_continuous_aggregate_policy`/`CREATE MATERIALIZED VIEW ... WITH (timescaledb.continuous)` cannot run inside a transaction block; support a first-line marker `-- migrate:no-transaction` that runs that file in autocommit mode.
6. `src/data_platform/app.py`: FastAPI app with `GET /health` returning `{"status":"ok","db":true|false}` (db = `SELECT 1` succeeds).
7. `src/data_platform/db.py`: a small connection helper (psycopg connection pool or simple `connect()` from `DATABASE_URL`).
8. `README.md`: replace the stub with Quickstart (local: copy `.env.example`, `docker compose up -d`, `pip install -e .[dev]`, `python -m data_platform.migrate`, `uvicorn data_platform.app:app`), and a Tiger Cloud section (set `DATABASE_URL` to the service URL with `sslmode=require`, run the same migrate command).
9. `tests/conftest.py`: a `db` fixture that connects with `DATABASE_URL` and skips the test (pytest.skip) when the DB is unreachable. Tests that need a DB use it.

## Acceptance criteria
- `docker compose up -d` brings up a healthy TimescaleDB.
- `python -m data_platform.migrate` run twice: first run applies 0000, second run applies nothing and exits 0.
- `GET /health` returns 200 with `db: true` against the compose DB.
- No secrets committed; `.env` ignored.

## Tests to run
- `pytest -q` with the compose DB up. Include `tests/test_migrate.py`: run the migrator twice against the DB, assert `schema_migrations` row count is unchanged on the second run and `timescaledb` extension exists. Include `tests/test_health.py` using FastAPI TestClient.
- Also run `pytest -q` with the DB stopped and confirm DB tests skip rather than fail.

## Out of scope
Any tables beyond `schema_migrations`. Ingestion. Read endpoints. Anything in `../contracts/`.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
