# Front-end integration (Vite / React / Vercel)

> Demo placeholder. No partnership, endorsement or real discount is implied. UI comes only from `design/`; this page only says which API each screen calls.

Three services, each with its own OpenAPI file in `contracts/api/`:

| Service | Local port | Contract | Owner |
|---|---|---|---|
| data-platform | 8001 | `data-platform.yaml` | Eren |
| insights-sponsors | 8002 | `insights-sponsors.yaml` | Eren |
| game-engine | 8003 | `game-engine.yaml` | Tobi |

Verify the wiring any time with `node scripts/connect-check.mjs` (optionally `--origin https://your-app.vercel.app`). It starts the services, then calls every endpoint below the way a browser on another origin would (CORS preflight with the Authorization header, then the real request).

## Configuration
Put the three base URLs in env vars, never hard-code them:

```
VITE_DATA_PLATFORM_URL=http://localhost:8001
VITE_INSIGHTS_URL=http://localhost:8002
VITE_GAME_ENGINE_URL=http://localhost:8003
```

Vite dev server alternative (no CORS needed locally), `vite.config.js`:

```js
server: { proxy: {
  '/api/dp':  { target: 'http://localhost:8001', rewrite: p => p.replace(/^\/api\/dp/, '') },
  '/api/is':  { target: 'http://localhost:8002', rewrite: p => p.replace(/^\/api\/is/, '') },
  '/api/ge':  { target: 'http://localhost:8003', rewrite: p => p.replace(/^\/api\/ge/, '') },
} }
```

## Auth (dev mode)
Every service uses the same dev scheme: `Authorization: Bearer <username>`. The same username works on all three. There is no real login or session issuer yet. Public (no token): `GET /loading-facts`, `GET /fun-facts`, and the data-platform read routes.

## CORS
data-platform allows any origin (GET). insights-sponsors allows GET, POST, DELETE with `Authorization` and `Content-Type`; set `CORS_ORIGINS=https://your-app.vercel.app` in its environment to restrict it. game-engine does not send CORS headers yet (issue to Tobi); until it does, call it through the Vite proxy or a server-side function.

## Hosting
Vercel hosts the front end only. The three Python services need a host of their own (any container or Python host) reachable over https from the Vercel origin (browsers block http calls from an https page), with `DATABASE_URL` set as an environment variable on the host. Start commands (from each service folder, `PYTHONPATH=src` for the first two): `uvicorn data_platform.app:app`, `DATA_BACKEND=postgres uvicorn insights_sponsors.main:app`, `uvicorn game_engine.app:app`. Dockerfiles are not written yet (data-platform queue item 015). The shared database holds real MBTA data and the demo rows; do not point a public deployment at it without reviewing access.

## Screen to endpoint map
Screens are the files in `design/canvas/`.

| Screen | Calls |
|---|---|
| Loading | insights `GET /loading-facts` (random facts, attribution included) |
| Home | insights `GET /stops/{id}/facts` (has `fallback` and `note` when no history is recorded), `GET /stops/{id}/content`, `GET /stops/{id}/nearby`; data-platform `GET /stops/{id}`, `GET /vehicles`; game-engine `GET /me/rank`, `GET /me/points`, `POST /checkins` |
| Traveled | data-platform `GET /me/travel` (total miles, miles per line, traveled segments, unlocked spots), `GET /lines`, `GET /routes` |
| Explore | insights `GET /categories`, `GET /labels`, `GET /stops/{id}/nearby` (category, label, match, sponsored, q, sort, limit, offset; `facets` for the chips), `GET /recommendations`, `GET /offers`, `GET /spots/{id}` |
| Faves | insights `GET /me/faves`, `POST` and `DELETE /me/faves/{fact_id}` |
| Profile | game-engine `GET /me/rank`, `GET /me/collection`; insights `GET /rank-tiers`, `GET /offers?rank=` |

## Display rules the API enforces
- Show `attribution` (and link `source_url`) for every fact and content item.
- Everything with `demo: true` is a placeholder; label it as such. Only `declared` or `certified` labels are ever returned.
- `needs_verify: true` content is hand-written text awaiting a human check.
- Facts about real places are real; sponsors, stores, offers and labels are demo placeholders.

## Known gaps
- game-engine CORS (see above).
- Along-line ordering for Explore is not built; unlocked spots stay empty until a service writes `visit` events (issue #64).
- Maps are placeholders in the design; Bryan rebuilds them from Boston GIS data.
