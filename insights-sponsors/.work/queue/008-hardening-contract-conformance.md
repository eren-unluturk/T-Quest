---
id: 008
title: Hardening, with a contract conformance test across all routes
status: ready
issue: 8
depends_on: [006]
---
## Goal
Make sure every implemented route matches the OpenAPI draft, then fix the small issues found in review, so clients can trust the contract.

## Context
- `insights-sponsors/openapi/insights-sponsors.yaml`
- `src/insights_sponsors/config.py` (review note: `env_file="../.env"` resolves from cwd)
- `src/insights_sponsors/main.py`, `routes/*`, `tests/*`
- `.work/ROADMAP.md` "Review notes"

## Steps
1. `config.py`: resolve the repo-root `.env` from the package location (`Path(__file__).resolve().parents[3] / ".env"`) instead of cwd. Missing file stays fine.
2. `tests/test_contract_conformance.py`: for every path and method in the YAML, call the running app (TestClient, with auth headers, seeded ids such as `place-pktrm`) and validate the 2xx JSON body against the response schema. Reuse the existing helper `tests/openapi_shape.py` (from 004: it follows `$ref`, handles `nullable`, and checks key sets and required keys). Extend it only if a schema feature it lacks shows up. Do not add jsonschema.
3. In the same test, fail if the app exposes a route that is not in the YAML (compare `app.routes` with the YAML paths, ignoring `/health`, `/docs`, `/openapi.json`, `/redoc`, `/docs/oauth2-redirect`).
4. Fix any mismatches the test finds in the code, not in the YAML. If the YAML itself is wrong, do not edit it: mark the prompt `blocked` and list the exact YAML change in the report so the planner can run the contract-change flow.
5. README: add a "Run locally" block with the exact commands on Windows PowerShell (`python -m pip install -e ".[dev]"`, `python -m pytest -q`, `python -m insights_sponsors.main`) and the env vars that matter.

## Acceptance criteria
- The conformance test covers every YAML operation and passes.
- No route exists outside the contract.
- `python -m pytest -q` passes.

## Tests to run
- `cd insights-sponsors && python -m pytest -q`

## Out of scope
- Changing the YAML. The Postgres backend (007).

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
