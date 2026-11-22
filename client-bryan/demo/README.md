# T-Quest local demo

Hackathon demo client (vanilla JS + MapLibre, no build step) that runs against the three local services.
Screens, copy, colors and the bubble nav follow Isabella's approved canvas (`design/canvas/`); the two maps
are rebuilt from Boston GIS data, as `design/canvas/README.md` asks.

## Run (four terminals, from the repo root)

```
# 1. data-platform: real Tiger Data database (needs DATABASE_URL in the root .env), read-only
cd data-platform && .venv/bin/uvicorn data_platform.app:app --port 8001

# 2. insights-sponsors: seed data in memory
cd insights-sponsors && .venv/bin/python -m insights_sponsors.main

# 3. game-engine: memory mode, so demo check-ins never write to the shared database
cd game-engine/src && env -u DATABASE_URL ../.venv/bin/uvicorn game_engine.app:app --port 8003

# 4. this demo
cd client-bryan/demo && node server.mjs      # http://localhost:4321
```

First-time setup for 1-3: `python3 -m venv .venv` then `.venv/bin/pip install -e ".[dev]"`
(game-engine: `.venv/bin/pip install -r requirements.txt`).

## Demo flow

Loading (fun facts) → Home → tap a pin for its fact, star it → **Tap in at Park Street** → pick a line and a stop →
**Ride there ⏩** (verified stamp + points) or **Tap out now** (a spoof, rejected) → Traveled → Explore → Faves → User page.
On Home, **Ethnic Boston** (bottom left of the map) shows pastel neighborhoods; tap one for T directions from your station, then **Show on map**.
On Home, tap empty map to move the demo rider; tap a 3D building for its card; 2D/3D toggles the tilt.

## Where the data comes from

| Piece | Source |
|---|---|
| Stations, live trains | data-platform (Tiger Data) |
| Line geometry, schedules for ride matching | public MBTA V3 API, cached by `server.mjs` |
| Basemap | OpenFreeMap (OpenStreetMap), recolored to the canvas palette |
| 3D iconic buildings | `public/data/iconic.geojson`, built by `node gis-build.mjs` (needs insights-sponsors): BPDA Building Roofprints footprints and heights, picked from Freedom Trail stops, Boston Landmarks Commission designations and the Hancock/Prudential towers |
| Ethnic Boston neighborhoods | `public/data/ethnic.geojson`, built by `node hoods-build.mjs`: City of Boston / BPDA neighborhood boundaries + curated heritage notes (wording to confirm with Isabella, #45) |
| T directions | Dijkstra over MBTA route patterns (ordered stops), ~2 min a stop, +5 min per change |
| Fun facts, stop facts (with source links), Freedom Trail, consent | insights-sponsors |
| Points, rank, collection, check-in | game-engine |
| Partner stores and perks (Explore, User page) | Isabella's FICTIONAL demo businesses, until Eren's real stores land |
| Faves, verified rides | browser localStorage (demo only). Traveled shows 3 sample rides until you verify one |

## Ride verification (prototype for issues #61 / #62)

Tap in at A, tap out at B. The ride counts only if: the speed between taps is under 80 km/h, and a real MBTA
scheduled trip left A around the tap-in and reached B within 3 min of the tap-out. A live train seen near A at
tap-in is shown as a soft signal. In the real app this runs in game-engine against Tiger Data vehicle history.

## Known gaps

- game-engine memory mode only scores Park Street, Downtown Crossing, Harvard, Alewife and South Station
  (`park`, `downtown`, ... ids); other stations verify but earn no points.
- The ride stamp, tap-in pill and ride sheet are not in the canvas yet: a proposal for Isabella, drawn in her style.
- Restarting game-engine or insights-sponsors resets points and consent (memory mode).
