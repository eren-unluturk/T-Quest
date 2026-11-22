# T-Quest web app

Vite + React + TypeScript. UI comes only from `design/` (see `docs/APP_SCOPE.md` for what is built and what is stubbed).

> Demo placeholder. No partnership, endorsement or real discount is implied. Demo. Not affiliated with the MBTA or any sponsor.

## Run locally
```
cd web
npm install
npm run dev          # ports the design, then starts Vite on http://localhost:5173
```
Start the three backends first (repo root: `node scripts/demo.mjs --serve`, or run them yourself on ports 8001, 8002, 8003). In dev the app calls `/api/dp`, `/api/is` and `/api/ge`, which Vite proxies to those ports, so no CORS setup is needed. Sign in with any sandbox username (3-32 letters or digits).

## Configuration
| Variable | Meaning |
|---|---|
| `VITE_DATA_PLATFORM_URL` | data-platform base URL (production builds require it) |
| `VITE_INSIGHTS_URL` | insights-sponsors base URL |
| `VITE_GAME_URL` | game-engine base URL |
| `DEV_DP_URL`, `DEV_IS_URL`, `DEV_GE_URL` | optional dev proxy targets |

If a variable is missing in a production build the app shows which one instead of failing silently.

## Scripts
`npm run dev`, `npm run build` (port, type-check, bundle), `npm run lint`, `npm run typecheck`, `npm test` (API client, session, view helpers, screens with a fake API), `npm run port` (regenerate `src/design/generated/` from `design/canvas/`).

## How it works
- `scripts/port-design.mjs` turns each `design/canvas/*.dc.html` into a React component (generated files are committed; do not edit them). Placeholder text in the design is replaced by real values through the bindings at the top of that script.
- `src/api/client.ts` is a typed client for the three services (timeouts, 401 sign-out, readable errors). `src/api/session.ts` keeps the token in memory only: no localStorage, no cookies, a reload signs you out.
- `src/screens/` wires each designed screen to data; screens without a design are plain stubs.

## Data honesty in the app
Demo spots show "Demo"; "LOCALLY OWNED" appears only for a declared or certified label returned by the API; pending labels are never returned. Attribution appears under the phone frame wherever content is shown, with the demo footer and data credits.

## Public hosting (future, not done)
The demo runs locally. For the deferred public plan see `docs/FUTURE_PUBLIC_HOSTING.md` (untested). Vercel would use: root directory `web`, build command `npm run build`, output `dist`, set the three `VITE_*` variables.

## Analytics tab
`src/screens/screens.tsx` `AnalyticsScreen` loads data-platform `GET /analytics/system` (live MBTA data) and, separately, the demo rider endpoints, so the live blocks still show if the rider services are down. `src/app/analytics.ts` turns the responses into the strings and SVG geometry that the generated `AnalyticsMarkup` renders; it contains no hard-coded numbers. The design source is `design/canvas/Analytics.dc.html` (authored by the admin; see `docs/APP_SCOPE.md`).
