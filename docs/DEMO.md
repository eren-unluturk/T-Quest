# Demo (backend tour)

> Demo placeholder. No partnership, endorsement or real discount is implied. Sponsors, stores, offers and labels are placeholders. Rider data is synthetic; MBTA data is real.

There is no rider UI yet (it waits on `design/`), so this demo shows the live backends. For UI beats see the placeholders in [PITCH.md](../PITCH.md).

## Run it
From the repo root, in PowerShell. A stale `DATABASE_URL` in your shell overrides `.env`, so clear it first:

```powershell
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
node scripts/demo.mjs            # starts the 3 services, runs the tour, stops them
node scripts/demo.mjs --serve    # same, then keeps them running (Ctrl+C to stop) so you can open the /docs pages
```

Needs: Python deps installed for each service, a reachable database in `.env`, and (for fresh live vehicles) the collector running: `python -m data_platform.collector` from `data-platform/`. Also available as the VS Code task "Demo tour".

If the nearby spots or content are empty, reload the seed (both idempotent, from `insights-sponsors/`): `python scripts/load_seed.py` then `python -m ingest_content.run`.

## What the tour shows (about 3 minutes)
1. **Real live MBTA data** from Tiger Data: Red Line vehicles reporting in the last 2 minutes, active alerts (data-platform :8001).
2. **Nearby spots at Harvard**, no filters, with filter chips (counts per category and label). Mint Julep shows no label because its only label is pending.
3. **Filters combine** on the fictional "Sample ... (demo)" spots: Davis, cafe + immigrant-owned; woman-owned returns nothing (only a pending label exists); Harvard asian-owned OR woman-owned; sponsored-first with native offers.
4. **Rank tiers** read from the shared `ranks` table (8 named ranks, placeholder percentages, top rank has a placeholder free item) and offers near Fenway.
5. **Tourist content near Park Street** with source link and attribution, plus loading-screen facts (hand-written, `needs_verify`).
6. **game-engine in in-memory demo mode** (fake stops "park" and "downtown", nothing written to the shared database): two check-ins, rank, quests. A repeat run within the cooldown shows HTTP 409; restart game-engine to reset.

## Where the Tiger Data numbers are
`docs/TIGER_DATA_RESULTS.md` (also copied into the generated block in PITCH.md). Real-data compression is TODO: measure; the continuous-aggregate latency comparison is reported as measured.

## Verified (local, 2026-11-21)
Run `node scripts/e2e-prod.mjs` (starts the three backends with `APP_ENV=prod`, a throwaway random `TOKEN_SECRET` and a throwaway CORS origin; game-engine in in-memory mode, so nothing is written to any database). Result: 47 of 47 checks passed.
- **Flow:** demo login issues a signed token; stops near Park Street (real MBTA data); check-in with the token; rank and points reflect it; nearby filter category plus label returns only the fictional Sample spot; a pending label never matches; offers by rank are all flagged demo; content items all carry attribution and source; travel returns the zero state for a new rider; fave and list faves.
- **Negative cases on game-engine, insights-sponsors and data-platform:** no token, garbage token, plain username (refused in prod), tampered signature, expired token and a token signed with another secret all answer 401 with a generic body.
- **CORS:** preflight from the exact origin is allowed; preflight and simple requests from another origin get no allow-origin header.
- **Hardening:** security headers present; `/docs` and `/openapi.json` hidden in prod; oversize body answers 413; invalid usernames answer 422; login is rate limited (429, with CORS headers); prod refuses to start without `TOKEN_SECRET` or with a wildcard `CORS_ORIGINS`.
- **Web app:** `npm run build`, type-check and lint pass; 28 unit and render tests pass; the app was opened in a real browser against the local backends (sign-in stub, Loading, Home and Explore rendered from real API data).

**Not verified:** Docker image builds (Docker unavailable), any container host, Vercel, https and proxy behavior, the seed script against a real second database (only `--dry-run` and the same-database refusal were checked), game-engine in Postgres mode against the demo database, the Traveled, Faves and Profile screens in a real browser (covered by render tests with a fake API only), rate limiting behind a proxy.

## Known limits
- No rider UI yet; it waits on `design/`.
- game-engine runs in in-memory demo mode with fake stops. We do not switch it to Postgres mode or write demo check-ins to shared tables, because that would put demo rows in the real database (and crowd the leaderboard tests). A repeat run within the cooldown returns HTTP 409; restart game-engine to reset the in-memory demo.
- Rider events are synthetic; the tour does not claim real users. Real check-ins arrive only once game-engine runs against the database with real riders.
- Freedom Trail text and loading facts are hand-written and await a human check.

### Real check-in aggregates (read-only SQL)
Use this when real or synthetic check-ins exist in `rider_events`. It only reads:

```sql
SELECT stop_id, count(*) AS checkins, count(DISTINCT user_id) AS riders,
       count(*) FILTER (WHERE is_synthetic) AS synthetic_checkins
  FROM rider_events
 WHERE event_type = 'checkin' AND time >= now() - interval '7 days'
 GROUP BY stop_id ORDER BY checkins DESC LIMIT 10;
```

Per-rider miles and traveled segments for the same data: `GET /me/travel` on data-platform (bearer token = username), which is also read-only.
