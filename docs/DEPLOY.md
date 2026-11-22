# Deploy the public demo (step by step, done by you)

> Demo placeholder. No partnership, endorsement or real discount is implied. Everything below is prepared but **not deployed**: no account, login or cloud command was run for you. The Dockerfiles are **untested** (Docker was not available when they were written), so do the local test in step 4 first.

## What gets deployed
| Piece | Where | Source |
|---|---|---|
| Demo database (separate Tiger Data service) | Tiger Cloud | `scripts/seed-demo-db.mjs` fills it |
| data-platform API | a container host | `data-platform/Dockerfile` |
| insights-sponsors API | a container host | `insights-sponsors/Dockerfile` |
| game-engine API | a container host | `game-engine/Dockerfile` |
| Web app | Vercel | `web/` |

The deployed backends must use the **demo** database only. Never put the real database URL on any host.

## 1. Create a separate Tiger Data demo service
Create a new, empty service in Tiger Cloud (free plan is fine; do not reuse the service that holds the live MBTA collector data). Copy its connection string. Keep it out of the repo, chat and logs.

## 2. Seed the demo database from your machine
Put the demo connection string in your local `.env` as `DEMO_DATABASE_URL` (never commit it). It must differ from `DATABASE_URL`; the script refuses to run otherwise and never prints connection strings.
```
node scripts/seed-demo-db.mjs --dry-run     # shows the plan, writes nothing
node scripts/seed-demo-db.mjs               # applies migrations, copies the MBTA stops/routes snapshot, loads the demo catalog, spots, labels, ranks, content
```
It copies only static MBTA data (lines, routes, stops, route_stops). No vehicles, predictions, alerts or rider data. Afterwards check in the Tiger Cloud console that the `stops`, `nearby_spots` and `content_items` tables have rows.

## 3. Generate secrets and decide the front-end URL
- `TOKEN_SECRET`: at least 16 random characters, the same value on all three backends. Example: `node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"`. Store it only in the hosts' environment settings.
- `CORS_ORIGINS`: the exact front-end URL, for example `https://your-app.vercel.app` (no wildcard, no trailing path). Prod refuses to start with a wildcard.

## 4. Test the images locally (Docker needed)
From the repo root:
```
docker build -f data-platform/Dockerfile -t tquest-data-platform .
docker build -f insights-sponsors/Dockerfile -t tquest-insights .
docker build -f game-engine/Dockerfile -t tquest-game-engine .
```
Run each with `-e APP_ENV=prod -e TOKEN_SECRET=... -e CORS_ORIGINS=... -e DATABASE_URL=<demo URL> -p <port>:<port>` and open `/health` (game-engine: `/healthz`). Fix anything that fails and tell the team.

## 5. Deploy the three backends on a container host
Any host that runs Docker images works (build context is the repo root; Dockerfile paths are above). Set these environment variables on each service:

| Variable | data-platform | insights-sponsors | game-engine |
|---|---|---|---|
| `APP_ENV` | `prod` | `prod` | `prod` |
| `TOKEN_SECRET` | same value | same value | same value |
| `CORS_ORIGINS` | exact front-end URL | exact front-end URL | exact front-end URL |
| `DATABASE_URL` | demo DB | demo DB | demo DB |
| `PORT` | host provides, or 8001 | 8002 | 8003 |
| `TRUST_PROXY` | `1` only if behind a proxy you control (so rate limits see the client IP) | same | same |
| `DATA_BACKEND` | | `postgres` (set in the image) | |
| `GE_ALLOW_DB_WRITES` | | | `1` only if you want game-engine to write demo rows to the demo database; every row it writes is flagged synthetic. Leave unset for read-only. |

The services use https from the host's front door; the web app needs https base URLs. Check `https://<service>/health` on each. `GET /docs` is intentionally off in prod.

## 6. Deploy the web app on Vercel
New project from the repo, **Root Directory** `web`, framework Vite, build `npm run build`, output `dist`. Environment variables:
```
VITE_DATA_PLATFORM_URL=https://<data-platform host>
VITE_INSIGHTS_URL=https://<insights host>
VITE_GAME_URL=https://<game-engine host>
```
Then set `CORS_ORIGINS` on the three backends to the Vercel URL you got (redeploy them).

## 7. Protect it while testing
Enable Vercel **Deployment Protection** (Standard or stronger) on the project while you test. Turn it off only right before judging, and turn it back on right after.

## 8. Smoke test the live URLs
Open the Vercel URL, sign in with a sandbox username, and walk Loading, Home, Explore, Faves, Profile. From your machine you can also run `node scripts/connect-check.mjs --origin https://your-app.vercel.app` against local services to re-check CORS behavior, and `node scripts/e2e-prod.mjs` to re-run the full local prod-mode check.

## Pre-launch safety checklist
- [ ] No real database credentials on any host or in Vercel; `DATABASE_URL` on every host is the **demo** service.
- [ ] `DEMO_DATABASE_URL` differs from `DATABASE_URL` (the seed script enforces it).
- [ ] `APP_ENV=prod`, same `TOKEN_SECRET` (16+ chars) on all three backends; none set in the repo.
- [ ] `CORS_ORIGINS` is the exact front-end URL on all three, no wildcard.
- [ ] Tokens expire (default 1 hour; `TOKEN_TTL_S` to change). The web app keeps the token in memory only.
- [ ] Rate limits on (on by default: writes 60/min, login 10/min per IP; `RATE_WRITE_PER_MIN`, `RATE_LOGIN_PER_MIN`). Set `TRUST_PROXY=1` behind a proxy.
- [ ] Demo footer visible on every screen: "Demo. Not affiliated with the MBTA or any sponsor. Transit data from the MBTA."
- [ ] Vercel Deployment Protection on until judging.
- [ ] Location and place tracking stay opt-in and off by default (place visits need explicit consent, coordinates rounded to about 100 m, 90-day retention). No personal data fields exist; usernames are sandbox names. game-engine check-ins use the rider's coordinates only to verify distance to the stop.
- [ ] `/docs` and `/openapi.json` are 404 on insights-sponsors and data-platform in prod.

## Teardown checklist
- [ ] Delete the Vercel project (or its deployments) and any custom domain.
- [ ] Delete the three backend services on the container host.
- [ ] Delete the demo Tiger Data service (this removes all demo rows).
- [ ] Rotate or delete `TOKEN_SECRET` everywhere it was set; remove `DEMO_DATABASE_URL` from your `.env`.
- [ ] If any credential ever appeared in a log, chat or screenshot, rotate it.

## Not verified here
Docker builds, the container host, Vercel, and https/proxy behavior. See "Verified" in `docs/DEMO.md` for what was checked locally.
