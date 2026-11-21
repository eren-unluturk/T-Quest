---
id: 005
title: Consent endpoints and the consent guard
status: ready
issue:
depends_on: [003]
---
## Goal
Opt-in consent that is stored, can be revoked, and is enforced in code before any non-MBTA location or place-visit data is used (definition of done in `AGENT.md`).

## Context
- `AGENT.md` (consent enforced before any non-MBTA tracking is used)
- `insights-sponsors/openapi/insights-sponsors.yaml` (`/consent` paths, `Consent`, `ConsentRequest`)
- `repo/base.py`, `repo/memory.py` (from 003)

## Steps
1. `src/insights_sponsors/routes/consent.py`: `GET /consent` returns one entry per scope (`location`, `place_visits`). Scopes never granted show `granted: false` with null timestamps. `POST /consent` grants a scope and returns 201. Re-granting updates `granted_at` and `policy_version` and clears `revoked_at`. `DELETE /consent/{scope}` revokes it and sets `revoked_at` (idempotent, 200). An unknown scope returns 422.
2. `src/insights_sponsors/consent.py`: `has_consent(repo, user_id, scope) -> bool` and a FastAPI dependency factory `require_consent(scope)` that raises 403 `{"detail": "consent required: <scope>"}`. Add the docstring: "Every read of non-MBTA location or place-visit data must go through has_consent/require_consent."
3. `CURRENT_POLICY_VERSION = "2026-11-21"` in `config.py`. Reject a POST whose `policy_version` differs with 409 `{"detail": "policy version mismatch", "current": ...}`.
4. Tests in `tests/test_consent.py`: default state, grant, revoke, re-grant, unknown scope, policy mismatch, 401 without auth, consents isolated per user, and `require_consent` on a throwaway test route returning 403 and then 200.

## Acceptance criteria
- Consent state round-trips through the repository (no state kept in the route module).
- `has_consent` is the single gate that the recommendations code (006) will call.
- `pytest` passes.

## Tests to run
- `cd insights-sponsors && pytest -q`

## Out of scope
- Collecting place visits (no ingest endpoint yet). Postgres persistence (008).

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
