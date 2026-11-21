---
id: 015
title: Dockerfile and compose services for the read API and ingestion worker
status: ready
depends_on: [014]
---
## Goal
One `docker compose --profile app up -d` brings up the DB, runs migrations, serves the read API on port 8001 and runs the MBTA ingestion worker, so teammates (game-engine, insights-sponsors, clients) can run data-platform locally or point it at Tiger Cloud without a Python setup.

## Context
- `docker-compose.yml`, `pyproject.toml`, `README.md`, `.env.example`
- `src/data_platform/app.py`, `migrate.py`, `load_static.py`, `ingest.py`
- Billing rule in `../AGENTS.md`: no Anthropic keys or pay-per-usage services anywhere

## Steps
1. `Dockerfile` (python:3.11-slim): install the package (no dev deps), copy `migrations/` and `seeds/`, non-root user, default command `uvicorn data_platform.app:app --host 0.0.0.0 --port 8001`. Add `.dockerignore` (.venv, .env, tests, bench output, verify output, .work).
2. `docker-compose.yml`: keep `db` as is (no profile, so `docker compose up -d` still starts only the DB). Add, under profile `app`:
   - `migrate`: same image, `command: python -m data_platform.migrate`, `depends_on: db (service_healthy)`, `restart: "no"`;
   - `api`: `ports: 8001:8001`, `depends_on: migrate (service_completed_successfully)`, healthcheck hitting `/health`;
   - `ingest`: `command: sh -c "python -m data_platform.load_static && python -m data_platform.ingest --interval 15"`, `depends_on: migrate (service_completed_successfully)`, `restart: unless-stopped`.
   All read `DATABASE_URL` and `MBTA_API_KEY` from `.env` via `env_file`, but inside compose override `DATABASE_URL` to `postgresql://postgres:${POSTGRES_PASSWORD:-postgres}@db:5432/tquest` unless `USE_EXTERNAL_DB=1`; document the Tiger Cloud variant (run only `api` and `ingest` with the Tiger URL, no `db`) in README.
3. If `MBTA_API_KEY` is empty, `ingest` logs a clear warning and keeps running with the public rate limit (do not crash-loop).
4. README "Run with Docker" section; state the API port 8001 (so it does not clash with other services on 8000).
5. Tests (no Docker needed): `tests/test_compose.py` loads `docker-compose.yml` with PyYAML and asserts the services, profiles, ports and depends_on conditions above; asserts `.dockerignore` excludes `.env`.

## Acceptance criteria
- Compose file structure test passes without Docker.
- `docker compose config` validates if Docker is available; if not, say so in the report.
- No secrets in the image (`.env` excluded).

## Tests to run
`pytest -q`

## Out of scope
Cloud deployment of the containers. Any other agent's services.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
