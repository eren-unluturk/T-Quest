# @tquest/map

The GIS maps from `client-bryan/demo`, ported to typed React components for the web app (`web/`).
Owner: client-bryan. `web/` belongs to Eren, so this folder only provides the components plus a patch that mounts them.

## What it adds

| Screen | Feature |
|---|---|
| Home | Live map in the design's map card: OpenStreetMap basemap recolored to the canvas palette, real MBTA lines and stations, live trains (data-platform), Boston landmarks in 3D from BPDA roofprints |
| Home | **Ethnic Boston** toggle: pastel neighborhoods (City of Boston boundaries). Tap one for T directions from your station, then **Show on map** |
| Home | **Tap in** inside the 75 m zone, pick where you get off, tap out. The ride counts only if a real MBTA scheduled train made that trip (prototype for #61 / #62). A verified ride calls back so the app can check in with game-engine |
| Traveled | The real network, ridden track solid and the rest dotted, miles measured along the real track, check pins on landmarks you unlocked |

## Mount it in web/ (one patch)

From the repo root:

```
git apply client-bryan/map/web-integration.patch
cd web && npm install
```

The patch:

- adds `maplibre-gl` 4.7.1 to `web/package.json`;
- in `vite.config.ts` and `vitest.config.ts`, resolves `@tquest/map` to this folder and dedupes React and MapLibre so there is one copy;
- in `vite.config.ts`, also lets the dev server read `..`;
- in `tsconfig.json`, maps `@tquest/map` and the React/MapLibre types to web's copies;
- in `screens.tsx`, mounts `HomeMap` and `TraveledMap` with `MapSlot`.

`MapSlot` finds the design's static map art (`HOME_MAP_CARD`, `TRAVELED_MAP`) and covers it with the live map, so the generated design markup stays untouched.

## Data

| Piece | Source |
|---|---|
| Stations, live trains | data-platform `/stops?route_id=`, `/vehicles` |
| Line shapes, route patterns, schedules | public MBTA V3 API, called from the browser (CORS-enabled, no key) |
| 3D landmarks | `data/iconic.geojson` (BPDA Building Roofprints + Boston Landmarks Commission; built by `../demo/gis-build.mjs`) |
| Ethnic Boston | `data/ethnic.geojson` (City of Boston neighborhood boundaries; heritage notes are curated, wording to confirm with Isabella, #45) |

## Develop

```
cd client-bryan/map && npm install
npm run typecheck && npm test
```

MapLibre is loaded on first use, so importing the module is safe in jsdom tests.

## Known gaps

- Ride verification runs in the browser, so it is a prototype. The real check belongs in game-engine (#61 / #62).
- The ride sheet, stamp and Ethnic Boston sheet are not in the canvas yet. They are proposals for Isabella, drawn in her style.
- T directions are estimates: 2 min a stop, 5 min per change.
