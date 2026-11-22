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
node scripts/demo-up.mjs       # data-platform 8001, insights-sponsors 8002, game-engine 8003, demo app 4321, React web app 5173; waits for health
```
Open **http://localhost:4321**: the demo app (`client-bryan/demo`, Isabella's screens with Boston GIS maps). It needs internet for the map tiles, fonts and the public MBTA schedule API. Ctrl+C stops everything it started. VS Code task: "Demo: start". If a port is taken the script names it and exits without starting anything. `node scripts/preflight.mjs --running` checks that all five answer. The React port in `web/` (http://127.0.0.1:5173) is the earlier build without real maps and is not the one we demo.

Backend-only tour (prints real calls, no UI): `node scripts/demo.mjs` (or `--serve` to keep the services up).

## What each screen shows (demo app, http://localhost:4321)
It runs against the three local services (no sign-in: the rider is a fixed demo user). Layout, copy and colors follow `design/canvas/`; the two maps are rebuilt from Boston GIS data. Details are in `client-bryan/demo/README.md`.

| Screen | Shows | Data from |
|---|---|---|
| Loading | Boston fun facts with sources while the app loads | insights-sponsors |
| Home | Map with live MBTA stations and trains, 2D/3D toggle with 3D landmark buildings (Boston open data), tappable spots with a fact each, star to save a fact, rank and points | data-platform (Tiger Data) for stations and trains; insights-sponsors; game-engine |
| Tap in / ride | Tap in at the nearest station, pick where you get off. **Ride there** skips the clock to the next real scheduled train and verifies the ride (speed check plus a matching MBTA scheduled trip); **Tap out now** is a spoof and is rejected. A verified ride earns points | MBTA V3 schedule (public API), game-engine in memory mode |
| Traveled | Verified rides and unlocked spots on a map; three sample rides are shown until you verify your own | browser localStorage |
| Explore | Nearby spots and perks from fictional demo businesses, filters by category, line and ownership label | demo data |
| Faves | Facts you starred | browser localStorage |
| User page | Rank, points, demo perks | game-engine (memory mode) |

**Not covered / stubs:** the check-in screen has no approved design (the tap-in sheet, ride stamp and ride sheet are a proposal drawn in the canvas style), and friends, leaderboard, quests and redemptions have no screens. **Ethnic Boston** (Home, bottom left) shows neighborhood boundaries with curated heritage notes; the wording is still to be confirmed (issue #45), so do not present it as verified. The rider name shown on the user page is hard-coded in the demo app.

## Known limits
- game-engine runs in its in-memory mode: points and ranks live in the process, reset when it restarts, and nothing is written to the database. In that mode it only scores Park Street, Downtown Crossing, Harvard, Alewife and South Station; a verified ride to any other station earns no points. A repeat ride to a stop within 30 minutes also earns none. Restart the demo (or just game-engine) to reset.
- Faves and rides are kept in the browser (localStorage), not in the database, so they survive reloads but not a new browser profile.
- Needs internet during the demo: OpenFreeMap tiles, Google Fonts, unpkg (MapLibre) and the public MBTA API (cached for an hour; without an `MBTA_API_KEY` set in the shell it is rate limited). Use the phone hotspot as a backup.
- The MBTA schedule query does not wrap past midnight, so rides near or after midnight cannot be verified (a small fix capping the window at 23:59 is in `client-bryan/demo/public/app.js`). Overnight there are no scheduled trains at all.
- Predictions are stored per platform id and the stops table has no platform-to-station link, so `/predictions?stop_id=place-...` returns nothing; no screen uses predictions. Query by `route_id` instead.
- Consent, place visits and analytics in insights-sponsors run on the in-memory backend with seed data.
- Rider data is synthetic; there are no real users yet. Sponsors, stores, offers and labels are demo placeholders. Rank percentages and the free item are placeholders.
- Freedom Trail text and loading facts are hand-written and await a human check.
- The older React app in `web/` writes faves to the database (`fact_faves`, flagged `is_demo`); the reset script below removes those.

## Recording the demo
With the demo running (`node scripts/demo-up.mjs`), in a second terminal:
```powershell
node scripts/record-demo.mjs        # about 2.7 minutes; overwrites docs/demo/tquest-demo.webm
```
It records the demo app: Loading, Home (map, 3D, a spot, a fave), a verified ride and a rejected spoof, Traveled, Explore with filters, Faves, the user page, and a closing card, with a caption strip under the phone frame (viewport 460x892: the 390x844 frame plus captions). Ride captions are chosen from what the screen shows (verified or not, points awarded). Flags: `--url`, `--out`, `--width`, `--height`, `--caption-height`, `--pace` (scales every pause). It needs internet, and uses Playwright from `web/node_modules` (run `npx playwright install chromium` once in `web/`). Restart game-engine (or `demo-up`) before recording so the ride earns points. `docs/demo/` is gitignored and each run overwrites the old file; the video is uploaded by hand. Re-record whenever the UI changes. ffmpeg is not needed (convert to MP4 yourself if wanted).

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
- **"No scheduled train" when you tap Ride there:** the public MBTA schedule API returned nothing (no internet, rate limited, after midnight, or service ended). Retry, set `MBTA_API_KEY` in the shell before `demo-up`, or skip the ride.
- **Every screen shows errors:** open http://127.0.0.1:8001/health. `"db": false` means the database is unreachable. `last_vehicle_at` is the newest vehicle timestamp (null if none in the last day).

## What the backend tour shows (about 3 minutes)
1. **Real live MBTA data** from Tiger Data: Red Line vehicles reporting in the last 2 minutes, active alerts (data-platform :8001).
2. **Nearby spots at Harvard**, no filters, with filter chips. Mint Julep shows no label because its only label is pending.
3. **Filters combine** on the fictional "Sample ... (demo)" spots: Davis, cafe + immigrant-owned; woman-owned returns nothing (only a pending label exists); Harvard asian-owned OR woman-owned; sponsored-first with native offers.
4. **Rank tiers** from the shared `ranks` table, and offers near Fenway.
5. **Tourist content near Park Street** with source link and attribution, plus loading-screen facts.
6. **game-engine in in-memory demo mode:** two check-ins, rank, quests. A repeat run within the cooldown shows HTTP 409; restart game-engine to reset.

## Where the Tiger Data numbers are
`docs/TIGER_DATA_RESULTS.md` (also copied into the generated block in PITCH.md). Real-data compression (one settled chunk per hypertable) and the continuous-aggregate latency comparison are reported there as measured.

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
