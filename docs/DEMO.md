# Demo runbook (local)

> Demo placeholder. No partnership, endorsement or real discount is implied. Sponsors, stores, offers and labels are placeholders. Rider data is synthetic; MBTA data is real.

The demo runs on one laptop: the three backends and the web app locally, reading our single Tiger Data database with the live MBTA data that the collector keeps filling. Nothing is hosted publicly (that is future work: [FUTURE_PUBLIC_HOSTING.md](FUTURE_PUBLIC_HOSTING.md)).

## Pre-demo checklist
- [ ] Laptop plugged in. Lid close action "Do nothing", sleep "Never", Windows updates paused.
- [ ] Collector running and fresh (newest vehicle row under 5 minutes old). Start it from `data-platform/`: `python -m data_platform.collector`.
- [ ] Phone hotspot ready as a backup network (the database is in the cloud).
- [ ] `.env` tab closed in the editor and not on screen.
- [ ] No stale `DATABASE_URL` in the shell: `Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue`.
- [ ] `node scripts/preflight.mjs` ends with "Preflight passed." (checks tools, env var names, database, collector freshness, `connect-check`). VS Code task: "Demo: preflight".

## Start and stop
```powershell
node scripts/demo-up.mjs       # data-platform 8001, insights-sponsors 8002, game-engine 8003, web 5173; waits for health
```
Open http://127.0.0.1:5173 and sign in with any sandbox username (letters and digits). Ctrl+C stops everything it started. VS Code task: "Demo: start". If a port is taken the script names it and exits without starting anything. `node scripts/preflight.mjs --running` checks that all four answer.

Backend-only tour (prints real calls, no UI): `node scripts/demo.mjs` (or `--serve` to keep the services up).

## What each screen shows
Data comes from the real endpoints. The services run in dev mode (plain sandbox username as bearer token; no `TOKEN_SECRET` or `CORS_ORIGINS` needed).

| Screen | Shows | Endpoints |
|---|---|---|
| Loading | A hand-written fact with its source and attribution | insights `/loading-facts` |
| Home | Park Street, stop facts, tourist content, rank and points, faved facts | data-platform `/stops/{id}`, insights `/stops/{id}/facts`, `/stops/{id}/content`, `/me/faves`, `/rank-tiers`, game-engine `/me/rank` |
| Traveled | Miles per line and traveled segments from check-ins (zeros without riders) | data-platform `/me/travel` |
| Explore | Nearby spots with category and label filters (declared or certified labels only; pending labels never leave the database), demo offers | insights `/stops/{id}/nearby`, `/categories`, `/labels`, `/offers` |
| Faves | Facts the rider saved | insights `/me/faves` |
| Profile | Rank tiers (8 named ranks, placeholder percentages), points | insights `/rank-tiers`, game-engine `/me/rank`, `/me/points` |

**Stubs (no approved design yet, so plain pages):** sign in, check in, friends, leaderboard, quests, redemptions. The check-in stub does call game-engine `/checkins`. Maps are placeholders. See [APP_SCOPE.md](APP_SCOPE.md).

## Known limits
- game-engine runs in its in-memory mode: check-ins, points and ranks live in the process, reset when it restarts, and nothing is written to the database. Its demo stop list includes the five real station ids the web app uses (Park Street, Harvard, Davis, Fenway, Kenmore); other stops answer "unknown stop". Postgres mode (`GE_ALLOW_DB_WRITES=1`) writes flagged demo rows that the reset below removes; we do not demo that by default.
- Faves are written to the database (`fact_faves`, flagged `is_demo`).
- Predictions are stored per platform id and the stops table has no platform-to-station link, so `/predictions?stop_id=place-...` returns nothing; no screen uses predictions. Query by `route_id` instead.
- Consent, place visits and analytics in insights-sponsors run on the in-memory backend with seed data.
- Rider data is synthetic; there are no real users yet. Sponsors, stores, offers and labels are demo placeholders. Rank percentages and the free item are placeholders.
- Freedom Trail text and loading facts are hand-written and await a human check.

## Recording the demo
With the demo running (`node scripts/demo-up.mjs`), in a second terminal:
```powershell
node scripts/record-demo.mjs        # about 2.3 minutes; writes docs/demo/tquest-demo.webm
```
It signs in with a sandbox username, walks the six built screens with a caption strip under the phone frame (the frame stays 390x844; the video is 390x940), and ends with a closing card. Flags: `--url`, `--user`, `--out`, `--width`, `--height`, `--caption-height`, `--pace` (scales every pause). It uses Playwright from `web/node_modules` (run `npx playwright install chromium` once in `web/`). It faves one fact and unfaves it again, so no demo row is left behind. `docs/demo/` is gitignored; the video is uploaded by hand. Convert to MP4 yourself if needed (ffmpeg is not required by the script).

## Reset demo rows
Only marked rows are removed: demo users (username starts with `demo_`) with their check-ins, points, badges, friends and redemptions, plus faves flagged `is_demo`. MBTA tables are never touched.
```powershell
node scripts/reset-demo.mjs         # DRY RUN: prints counts, deletes nothing
node scripts/reset-demo.mjs --yes   # prints counts, then deletes them
```
VS Code task: "Demo: reset demo rows" (dry run).

## Run it on a teammate's machine
1. `git pull` main. Install: `pip install -e data-platform -e insights-sponsors` and `pip install -r game-engine/requirements.txt`; then `cd web && npm install`.
2. Copy `.env.example` to `.env` and ask Eren for the database URL (never commit it or paste it in chat).
3. `node scripts/preflight.mjs`, then `node scripts/demo-up.mjs`. The collector runs on Eren's laptop; if it is off, preflight reports stale data and the live vehicles are old.

## Troubleshooting
- **Wrong database, "password authentication failed", or old data after editing `.env`:** a `DATABASE_URL` in the shell overrides `.env`. `Remove-Item Env:DATABASE_URL`, open a new terminal, rerun. Preflight warns about this.
- **`ModuleNotFoundError: data_platform` (or `insights_sponsors`):** a service was started by hand without `PYTHONPATH=src`. Use `demo-up.mjs`, or `$env:PYTHONPATH='src'` from the service folder.
- **Port in use:** `demo-up.mjs` names the port. `Get-NetTCPConnection -LocalPort 8001 | Select OwningProcess`, then stop that leftover demo process (never the collector).
- **Collector stale ("newest vehicle row is N min old"):** the collector is not running or lost its network. Restart it from `data-platform/` with `python -m data_platform.collector`.
- **Empty nearby spots or content:** reload the seed (idempotent, from `insights-sponsors/`): `python scripts/load_seed.py`, then `python -m ingest_content.run`.
- **Every screen shows errors:** open http://127.0.0.1:8001/health. `"db": false` means the database is unreachable. `last_vehicle_at` is the newest vehicle timestamp (null if none in the last day).

## What the backend tour shows (about 3 minutes)
1. **Real live MBTA data** from Tiger Data: Red Line vehicles reporting in the last 2 minutes, active alerts (data-platform :8001).
2. **Nearby spots at Harvard**, no filters, with filter chips. Mint Julep shows no label because its only label is pending.
3. **Filters combine** on the fictional "Sample ... (demo)" spots: Davis, cafe + immigrant-owned; woman-owned returns nothing (only a pending label exists); Harvard asian-owned OR woman-owned; sponsored-first with native offers.
4. **Rank tiers** from the shared `ranks` table, and offers near Fenway.
5. **Tourist content near Park Street** with source link and attribution, plus loading-screen facts.
6. **game-engine in in-memory demo mode:** two check-ins, rank, quests. A repeat run within the cooldown shows HTTP 409; restart game-engine to reset.

## Where the Tiger Data numbers are
`docs/TIGER_DATA_RESULTS.md` (also copied into the generated block in PITCH.md). Real-data compression is TODO: measure; the continuous-aggregate latency comparison is reported as measured.

## Verified (local, 2026-11-21)
Run `node scripts/e2e-prod.mjs` (starts the three backends with `APP_ENV=prod`, a throwaway random `TOKEN_SECRET` and a throwaway CORS origin; game-engine in in-memory mode, so nothing is written to any database). Result: 47 of 47 checks passed.
- **Flow:** demo login issues a signed token; stops near Park Street (real MBTA data); check-in with the token; rank and points reflect it; nearby filter category plus label returns only the fictional Sample spot; a pending label never matches; offers by rank are all flagged demo; content items all carry attribution and source; travel returns the zero state for a new rider; fave and list faves.
- **Negative cases on game-engine, insights-sponsors and data-platform:** no token, garbage token, plain username (refused in prod), tampered signature, expired token and a token signed with another secret all answer 401 with a generic body.
- **CORS:** preflight from the exact origin is allowed; preflight and simple requests from another origin get no allow-origin header.
- **Hardening:** security headers present; `/docs` and `/openapi.json` hidden in prod; oversize body answers 413; invalid usernames answer 422; login is rate limited (429, with CORS headers); prod refuses to start without `TOKEN_SECRET` or with a wildcard `CORS_ORIGINS`.
- **Web app:** `npm run build`, type-check and lint pass; 28 unit and render tests pass; the app was opened in a real browser against the local backends (sign-in stub, Loading, Home and Explore rendered from real API data).

**Not verified:** Public hosting was not done (see FUTURE_PUBLIC_HOSTING.md). Not checked: Docker image builds, any container host, Vercel, https and proxy behavior, the seed script against a real second database (only `--dry-run` and the same-database refusal were checked), game-engine in Postgres mode against the demo database, the Traveled, Faves and Profile screens in a real browser (covered by render tests with a fake API only), rate limiting behind a proxy.

## Real check-in aggregates (read-only SQL)
Use this when real or synthetic check-ins exist in `rider_events`. It only reads:

```sql
SELECT stop_id, count(*) AS checkins, count(DISTINCT user_id) AS riders,
       count(*) FILTER (WHERE is_synthetic) AS synthetic_checkins
  FROM rider_events
 WHERE event_type = 'checkin' AND time >= now() - interval '7 days'
 GROUP BY stop_id ORDER BY checkins DESC LIMIT 10;
```

Per-rider miles and traveled segments for the same data: `GET /me/travel` on data-platform (bearer token = username), which is also read-only.
