# Rehearsal run sheet (3 minutes)

> Demo placeholder. No partnership, endorsement or real discount is implied. Sponsors, offers and labels are placeholders. Rider data is synthetic; MBTA data is real.

Built from the demo script in [PITCH.md](../PITCH.md) and the runbook in [DEMO.md](DEMO.md). The demo app is `client-bryan/demo` (http://localhost:4321). A captioned recording (`node scripts/record-demo.mjs`, see DEMO.md) is the backup if the live demo fails.

## Before every rehearsal
```powershell
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
node scripts/preflight.mjs          # must end with "Preflight passed."
node scripts/demo-up.mjs            # starts the 3 backends, the demo app and the React app, prints the URLs
```
Open http://localhost:4321 (the demo app with the maps; needs internet). Restart `demo-up` before each full run so game-engine starts with no collected stops (otherwise a repeat ride earns no points). Ctrl+C in the demo-up terminal stops everything. Afterwards `node scripts/reset-demo.mjs` (dry run) shows what the demo wrote to the database (normally nothing: faves and rides stay in the browser).

## Who says what (TODO: assign)
| Part | Speaker |
|---|---|
| Hook and problem | TODO: name |
| Home and Explore (driving the app) | TODO: name |
| Live data and Tiger Data numbers | TODO: name |
| Profile and close | TODO: name |

## Run sheet
| Time | Click | Say | Notes |
|---|---|---|---|
| 0:00 | Title slide | The 30-second hook from PITCH.md. | Say once that this is a demo with placeholders. |
| 0:30 | **Loading, then Home** | Boston fun facts load first; Home is a Boston map with live MBTA stations and trains from Tiger Data. Toggle 3D for the landmark buildings. | Map tiles need internet. |
| 1:00 | **Tap in at Park Street, Ride there** | The ride is checked against the real MBTA schedule and earns points from game-engine (demo mode). Then tap in again and **Tap out now**: it is rejected as a spoof. | The tap-in sheet and ride stamp are a proposal, not in the approved canvas. Only Park Street, Downtown Crossing, Harvard, Alewife and South Station score points. |
| 1:30 | **Live data moment:** the trains on the Home map, or `http://127.0.0.1:8001/vehicles?route_id=Red` in a tab | Vehicles on the line right now come from the MBTA feed our collector stores in Tiger Data. | Check `last_vehicle_at` at `http://127.0.0.1:8001/health` is under 5 minutes old. |
| 2:00 | Slide: Tiger Data numbers | Read only the figures in the generated block in PITCH.md / `docs/TIGER_DATA_RESULTS.md`. | If a figure says "TODO: measure", say it is still being measured. Do not add numbers. |
| 2:20 | **Explore** | Nearby spots and perks from fictional demo businesses; filter by category, line and ownership label. | Everything shown is a demo placeholder. |
| 2:40 | **User page** | Rank and points from game-engine; demo perks. No real partnerships. | Friends, leaderboard, quests and redemptions have no screens yet. |
| 2:50 | Close | What we would do next: more lines, the tourist layer, a possible sponsor program (not pursued now). | Public hosting is future work; do not imply a public URL. Do not present Ethnic Boston as verified (wording unconfirmed). |

## 60-second version
1. (0:00) One sentence of hook and "this is a demo with placeholders".
2. (0:10) **Home**: the live map, a fact with its source.
3. (0:25) **Tap in, Ride there**: verified against the real schedule, points.
4. (0:40) Live vehicles, `last_vehicle_at` fresh.
5. (0:55) Close: "real MBTA data, synthetic riders, demo sponsors".

## If something fails
| Problem | Do this |
|---|---|
| Collector stale (preflight says "N min old", or `last_vehicle_at` is old) | Restart it from `data-platform/`: `python -m data_platform.collector`; vehicles reappear within about a minute. If it cannot be fixed, say the feed is paused and show the numbers slide instead; do not call old data live. |
| A service is down / a screen shows errors | Check `http://127.0.0.1:8001/health` (`"db": false` = database unreachable). Stop with Ctrl+C and run `node scripts/demo-up.mjs` again; it names any port still in use. |
| No wifi | Switch to the phone hotspot (the database, map tiles and MBTA schedule are all online). If there is still no connection, show the recording and say so. |
| Wrong database / old data | A stale `DATABASE_URL` in the shell overrides `.env`: `Remove-Item Env:DATABASE_URL`, open a new terminal, rerun preflight. |
| Ride says no scheduled train, or points are missing | No internet or the MBTA API is rate limited, it is after midnight, or the stop was already collected in the last 30 min. Restart `demo-up` to reset game-engine, or show the earlier recording. The check-in screen design is still pending; fallback: `node scripts/demo.mjs` does two check-ins against game-engine and shows rank and quests. |
| Friends, leaderboard, quests, redemptions | They have no screens in the demo app; say "no approved design yet" and move on. |

## Judge questions (from PITCH.md Q&A)
- **Is the rider data real?** No. There are no users yet. Stops, routes, schedules, live vehicles, predictions and alerts are real MBTA data. Rider events are synthetic, flagged `is_synthetic`, and we say so.
- **Are the sponsors real?** No. The Red Sox, Mint Julep and Diesel Cafe entries are demo placeholders. No partnership, endorsement or real discount is implied. We are not pursuing real partnerships.
- **How are identity labels verified?** Only when the business declared the label itself or an official certification or directory lists it. We store the evidence URL or declaration note, the date and who verified it. Never inferred from names, photos or reviews. Pending labels are never shown or matched by filters.
- **What if a business is listed wrongly?** There is a correction and removal path in `docs/DATA_SOURCES.md`.
- **Where does the tourist content come from?** Official APIs and downloads of open sources, with license and attribution stored for each record; we do not scrape.
- **Is compression a big win?** We report the numbers as measured (`docs/TIGER_DATA_RESULTS.md`). The real-data run is small, so we do not claim more than it shows.
- **Privacy?** Location tracking beyond check-ins is opt-in and revocable, coordinates are rounded, and city analytics hide groups under three riders.
- **Does it cost per token?** No. No LLM or API-key billing anywhere in the product.
- **Why isn't it deployed publicly?** A deliberate choice for a demo on live data: our single database holds the live MBTA stream and its credentials, the container images were never tested, the game engine keeps state in memory by default, and the default login is for local demos only. A production mode exists but is off by default; public hosting is documented as future work.
