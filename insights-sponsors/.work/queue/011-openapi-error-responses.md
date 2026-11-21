---
id: 011
title: Document consent error responses in the OpenAPI draft
status: ready
issue: 8
depends_on: [005]
---
## Goal
The draft spec must list every status code the service returns, so client-bryan can handle them. 005 added a 409 (policy mismatch) and a 403 consent gate that are not documented yet. The draft has not been promoted to `contracts/` yet, so it can still change in our folder.

## Context
- `insights-sponsors/openapi/insights-sponsors.yaml`
- `src/insights_sponsors/routes/consent.py`, `src/insights_sponsors/consent.py`
- Report `.work/reports/005.md` (Deviations)
- `src/insights_sponsors/routes/insights.py` (from 006, if present): which routes use consent

## Steps
1. Add a schema `PolicyMismatch` {detail: string, current: string} and a `409` response on `POST /consent` that uses it.
2. Add a reusable response `components.responses.ConsentRequired` (403, `Error` schema, description "consent required: <scope>").
3. `GET /recommendations` does not return 403. It silently skips place-visit signals without consent. Add that sentence to its description. Reference `ConsentRequired` only from routes that actually use `require_consent`. If none do yet, keep it in components for future routes and say so in the description of `/consent`.
4. Add `info.x-changelog` with an entry `0.1.1: document 409 on POST /consent and ConsentRequired`. Bump `info.version` to `0.1.1`.
5. Extend `tests/test_openapi.py`: POST /consent documents 409 with `PolicyMismatch`, and `components.responses.ConsentRequired` exists. Add a test that the 409 body returned by the app matches `PolicyMismatch` (reuse `tests/openapi_shape.py`).

## Acceptance criteria
- The spec validates, version is 0.1.1, and the new tests pass.
- `python -m pytest -q` passes.
- Nothing written under `../contracts/`.

## Tests to run
- `cd insights-sponsors && python -m pytest -q`

## Out of scope
- New routes. Promoting to `contracts/` (human step, #26).

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
