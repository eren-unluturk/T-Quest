---
id: 017
title: Validate place-visit store_id and add a demo smoke script
status: ready
issue:
depends_on: [016]
---
## Goal
Two small hardening items before the demo. First, `POST /place-visits` accepts any `store_id` (report 013), which in postgres mode is a uuid column, so a bad value would give a 500. Second, the team needs one command that exercises every route with demo users and prints a readable summary for the presentation.

## Context
- Report `.work/reports/013.md` (Deviations: store_id is not validated)
- `src/insights_sponsors/routes/place_visits.py`, `repo/base.py`, `repo/memory.py`, `repo/postgres.py` (from 014/016), `repo/ids.py`
- `insights-sponsors/openapi/insights-sponsors.yaml` (0.3.0)
- `tests/test_contract_conformance.py`

## Steps
1. `POST /place-visits`: if `store_id` is given, it must resolve to an existing active store via a new repo method `store_exists(store_id) -> bool`. In postgres mode, accept either a uuid or a seed slug and map slugs with `repo/ids.py`. Return 422 `{"detail": "unknown store_id"}` otherwise. A malformed uuid must also give 422, never 500. Update the 422 description in the YAML (no version bump needed for a description change, but add an `x-changelog` line "0.3.0: clarify 422 for unknown store_id").
2. The memory backend also purges visits older than 90 days on write (not only filters them on read), so memory use stays bounded. Add a test.
3. `insights-sponsors/scripts/demo_smoke.py`: starts the app in-process (TestClient; no network, no keys) in memory mode, or in postgres mode with `--postgres` (uses `DATABASE_URL`). As `user-1`:
   - grant `place_visits`
   - post one visit
   - call every GET route in the spec, plus revoke and the DELETE routes

   Print a short human-readable summary per route (status, item counts, `home_line`, top 3 recommendations with reasons, busiest stop, one fun fact). Exit non-zero on any non-2xx (except the expected 403 case, which it demonstrates explicitly by calling `POST /place-visits` once without consent first). Keep the output under about 60 lines.
4. Tests: store_id valid/unknown/malformed (both backends where a DB is available; memory always), retention purge, and `demo_smoke.main(["--quiet"])` returning 0 in memory mode.
5. README: a "Demo" section with the smoke command.

## Acceptance criteria
- No input to `POST /place-visits` can produce a 500 (test malformed uuid, slug, unknown).
- `python scripts/demo_smoke.py` exits 0 in memory mode and prints the summary.
- `python -m pytest -q` passes.

## Tests to run
- `cd insights-sponsors && python -m pytest -q && python scripts/demo_smoke.py`

## Out of scope
- New routes. Paid services of any kind.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
