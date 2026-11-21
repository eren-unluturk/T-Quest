---
id: 001
title: Scaffold the insights-sponsors FastAPI service
status: done
issue:
depends_on: []
---
## Goal
A runnable, tested Python 3.11+ FastAPI service skeleton for insights-sponsors, with config, a fake-able auth dependency and a health route. Everything later builds on this.

## Context
- `../DECISIONS.md` D1 (FastAPI, one service per agent), D2 (shared Tiger Data DB)
- `../.env.example` (INSIGHTS_SPONSORS_PORT=8002, DATABASE_URL)
- `../game-engine/src/game_engine/` and `../game-engine/tests/test_rules.py` for the house layout (src layout, pytest). Read only.
- `../contracts/api/game-engine.yaml` for the auth convention: bearer token on every route, user id from the session.

## Steps
1. Create `insights-sponsors/pyproject.toml` (name `insights-sponsors`, requires-python >=3.11, src layout, package `insights_sponsors`). Runtime deps: fastapi, uvicorn[standard], pydantic>=2, pydantic-settings, psycopg[binary]>=3. Dev extras `[dev]`: pytest, httpx, openapi-spec-validator, pyyaml. Configure pytest `pythonpath = ["src"]` and `testpaths = ["tests"]`.
2. Create `src/insights_sponsors/__init__.py`, `config.py` (pydantic-settings `Settings`: `database_url: str | None = None`, `port: int = 8002` read from `INSIGHTS_SPONSORS_PORT`, `auth_mode: Literal["dev","strict"] = "dev"`, `data_backend: Literal["memory","postgres"] = "memory"`; reads `../.env` if present, never required).
3. Create `src/insights_sponsors/auth.py`: FastAPI dependency `current_user_id()` that requires `Authorization: Bearer <token>`. In `auth_mode == "dev"` the token itself is the user id (non-empty string). In `strict` mode raise 501 with detail "session verification not wired yet". Missing or malformed header returns 401.
4. Create `src/insights_sponsors/main.py`: `create_app()` factory and module-level `app`. Route `GET /health` (no auth) returning `{"status":"ok","service":"insights-sponsors","data_backend": <setting>}`. Add `if __name__ == "__main__"` that runs uvicorn on `settings.port`.
5. Create `tests/conftest.py` with a `client` fixture (TestClient on `create_app()`) and an `auth_headers` fixture (`{"Authorization": "Bearer user-1"}`).
6. Create `tests/test_health.py` and `tests/test_auth.py` (a tiny test-only route is fine, or test the dependency directly): 401 without header, 401 on `Basic x`, user id returned in dev mode.
7. Update `insights-sponsors/README.md` with: install (`pip install -e ".[dev]"`), run (`python -m insights_sponsors.main`), test (`pytest`). Keep the existing paragraph.
8. Add `insights-sponsors/.gitignore` for `__pycache__/`, `.pytest_cache/`, `*.egg-info/`, `.venv/`.

## Acceptance criteria
- `pip install -e ".[dev]"` succeeds from `insights-sponsors/`.
- `pytest` passes.
- `python -m insights_sponsors.main` serves `/health` on port 8002.
- No file written outside `insights-sponsors/`.

## Tests to run
- `cd insights-sponsors && pip install -e ".[dev]" && pytest -q`

## Out of scope
- Database access, any business endpoint, OpenAPI file (002), real session verification.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
