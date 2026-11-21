---
id: 013
title: Consented place-visit ingest (POST /place-visits) and deletion on revoke
status: done
issue:
depends_on: [012]
---
## Goal
The brief asks for opt-in tracking of other places visited (restaurants and so on) to improve recommendations, but nothing records place visits yet. Add an ingest route that only works with `place_visits` consent, and make revoking consent delete that user's stored visits. This is the first route using `require_consent`.

## Context
- `src/insights_sponsors/consent.py` (`require_consent`, `has_consent`), `routes/consent.py`
- `src/insights_sponsors/repo/base.py`, `repo/memory.py` (`place_visits` from 006)
- `insights-sponsors/openapi/insights-sponsors.yaml` (`components.responses.ConsentRequired` from 011; version 0.2.0 after 012)
- `../docs/PROJECT_BRIEF.md` "Consent"; data-platform's #22 ACK: `place_visits` hypertable with 90-day retention

## Steps
1. OpenAPI: `POST /place-visits` (bearer auth), body `PlaceVisitIn` {lat (number, -90 to 90), lon (number, -180 to 180), visited_at (date-time), place_category enum[food, clothing, sports, other], store_id nullable}. Responses: 201 `PlaceVisitAck` {accepted: true, retained_days: 90}, 401, 403 `ConsentRequired`, 422. Also `DELETE /place-visits` (bearer auth) -> 200 {deleted: integer}, which works without consent so users can always erase. Bump to `0.3.0` with a changelog entry. Put the privacy rules in the descriptions: coordinates are rounded to 3 decimals (about 100 m) before storage, `visited_at` more than 7 days old or more than 5 minutes in the future is rejected with 422, and data is kept 90 days.
2. Repository: `add_place_visit(user_id, visit)` and `delete_place_visits(user_id) -> int` on the Protocol and the memory backend. The memory backend enforces 90-day retention on read.
3. Route module `routes/place_visits.py`: POST uses `Depends(require_consent("place_visits"))`, rounds coordinates, and validates the time window. DELETE calls `delete_place_visits`.
4. In `routes/consent.py`, `DELETE /consent/place_visits` also calls `delete_place_visits` for that user. Document it on the consent DELETE description ("revoking place_visits deletes stored place visits").
5. Tests in `tests/test_place_visits.py`: 403 without consent (body `consent required: place_visits`), 201 with consent, coordinates stored rounded, 422 for an old, future or out-of-range visit, `location` consent alone is not enough, revoking consent deletes the visits and recommendations then show no place affinity, DELETE /place-visits works without consent and returns the count, and 401 without auth. Shape checks via `tests/openapi_shape.py`.

## Acceptance criteria
- No place visit can be stored without `place_visits` consent. Tests prove it.
- Revoking consent leaves zero stored visits for the user.
- The spec validates at 0.3.0, and `python -m pytest -q` passes.

## Tests to run
- `cd insights-sponsors && python -m pytest -q`

## Out of scope
- Client-side location collection. Store matching from coordinates. The Postgres backend.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
