---
id: 010
title: Broaden seed coverage (neighborhoods and bus) and check coordinates against the MBTA V3 API
status: done
issue:
depends_on: [006]
---
## Goal
Recommendations need variety: today 5 of 13 seeded stops are Downtown and none are bus stops, while the brief requires bus parity. Add stops across more neighborhoods, including bus stops, and check every stop's coordinates and name against the real MBTA V3 API so demo data is correct.

## Context
- `insights-sponsors/data/seed/*.json`, `src/insights_sponsors/repo/memory.py`, `tests/test_memory_repo.py`
- Report `.work/reports/003.md` (coordinates were approximate, about 50 m; source URLs not checked)
- MBTA V3 API: `GET https://api-v3.mbta.com/stops/{id}` and `GET https://api-v3.mbta.com/stops?filter[route]=<route>`. It works without a key at low rates. If `MBTA_API_KEY` is set in the environment, send it as the `x-api-key` header. Never commit a key.

## Steps
1. Add `insights-sponsors/scripts/verify_stops.py`: for every stop in `stops.json`, fetch `/stops/{id}` and print id, seed name vs API name, and the distance in metres between seed and API coordinates. Exit non-zero if any id is unknown or any name differs. Option `--write` updates lat/lon (and name) in `stops.json` from the API. Use only `urllib` from the standard library, and sleep 0.3 s between calls.
2. Add at least 10 more stops so the seed covers at least 8 distinct neighborhoods (for example Jamaica Plain `place-jaksn`, Somerville/Davis `place-davis`, Seaport `place-crtst` or a Silver Line stop, East Boston `place-mvbcl`, Dorchester `place-jfk`, South End `place-bbsta` already exists so pick `place-masta`, Allston/Brighton on the Green B branch, Charlestown already exists). Include at least 3 bus stops (real numeric MBTA bus stop ids, `mode: "bus"`) on high-ridership routes such as 1, 28, 39 or 66. Take ids, names and coordinates from the API, not from memory.
3. Give each new stop 1-2 accurate facts in `stop_facts.json` (`fast_fact` is fine for bus stops: route and neighborhood context).
4. Run `verify_stops.py --write`, then run it again without `--write` and confirm it exits 0. Paste the output summary into the report.
5. Re-check `freedom_trail.json` `nearest_stop_id` against the corrected coordinates (pick the closest seeded subway stop by haversine). Update it if that changes anything.
6. Add 2 fictional stores with offers near new non-Downtown stops so local picks exist outside Downtown.
7. Extend the tests: at least 8 neighborhoods, at least 3 bus stops, every trail site's `nearest_stop_id` is the closest seeded subway stop, and every non-null `source_url` starts with `https://`.
8. Keep `rider_events.json` from 006 consistent. If you add stops, you may regenerate events, but keep `user-1`'s home line and the hand-checked numbers in the 006 tests valid. Otherwise update those test expectations and explain why in the report.

## Acceptance criteria
- `python scripts/verify_stops.py` exits 0 (network required, so run it manually; do not call it from pytest).
- Seed has 23 or more stops, 8 or more neighborhoods, and 3 or more bus stops.
- `python -m pytest -q` passes.

## Tests to run
- `cd insights-sponsors && python scripts/verify_stops.py && python -m pytest -q`

## Out of scope
- Full GTFS import (data-platform owns ingestion). Changing the OpenAPI contract.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
