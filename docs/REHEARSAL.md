# Rehearsal run sheet (3 minutes)

> Demo placeholder. No partnership, endorsement or real discount is implied. Sponsors, offers and labels are placeholders. Rider data is synthetic; MBTA data is real.

Built from the demo script in [PITCH.md](../PITCH.md) and the runbook in [DEMO.md](DEMO.md). Moments that come from the approved design are marked **[UI]**; screens without a design are **[STUB]** (plain pages).

## Before every rehearsal
```powershell
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
node scripts/preflight.mjs          # must end with "Preflight passed."
node scripts/demo-up.mjs            # starts the 3 backends and the web app, prints the URLs
```
Open http://127.0.0.1:5173 and sign in with a sandbox username. Ctrl+C in the demo-up terminal stops everything. Afterwards, `node scripts/reset-demo.mjs` (dry run) shows what the demo wrote; add `--yes` to delete it.

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
| 0:30 | **[UI] Home** (sign in first) | Park Street scene: a real fact with its source, the rider's rank and points. | Check-in is a **[STUB]** plain page; do not click it live (see fallback). |
| 1:00 | **[UI] Explore** | Nearby spots at a stop. Open the owner filter and pick a label: only the fictional "Sample ... (demo)" spots show labels. Real businesses show none. | Pending labels are never shown. Sponsors and offers are demo placeholders. |
| 1:30 | **Live data moment:** `http://127.0.0.1:8001/vehicles?route_id=Red` in a browser tab, or `node scripts/demo.mjs` step 1 | Vehicles on the Red Line right now, from the MBTA live feed our collector stores in Tiger Data. | Check `last_vehicle_at` at `http://127.0.0.1:8001/health` is under 5 minutes old. There is no map screen (maps are placeholders). |
| 2:00 | Slide: Tiger Data numbers | Read only the figures in the generated block in PITCH.md / `docs/TIGER_DATA_RESULTS.md`. | If a figure says "TODO: measure", say it is still being measured. Do not add numbers. |
| 2:30 | **[UI] Profile** | Rank tiers and demo offers. Redemption has no design yet (**[STUB]**). | Say clearly that offers are demo placeholders and the rank percentages are placeholders. |
| 2:50 | Close | What we would do next: more lines, the tourist layer, a possible sponsor program (not pursued now). | Public hosting is future work; do not imply a public URL. |

## 60-second version
1. (0:00) One sentence of hook and "this is a demo with placeholders".
2. (0:10) **Home**: real fact with source, rank and points.
3. (0:25) **Explore**: one label filter on a Sample spot.
4. (0:40) Live vehicles tab, `last_vehicle_at` fresh.
5. (0:55) Close: "real MBTA data, synthetic riders, demo sponsors".

## If something fails
| Problem | Do this |
|---|---|
| Collector stale (preflight says "N min old", or `last_vehicle_at` is old) | Restart it from `data-platform/`: `python -m data_platform.collector`; vehicles reappear within about a minute. If it cannot be fixed, say the feed is paused and show the numbers slide instead; do not call old data live. |
| A service is down / a screen shows errors | Check `http://127.0.0.1:8001/health` (`"db": false` = database unreachable). Stop with Ctrl+C and run `node scripts/demo-up.mjs` again; it names any port still in use. |
| No wifi | Switch to the phone hotspot (the database is in the cloud). If there is still no connection, show screenshots or the recording and say so. |
| Wrong database / old data | A stale `DATABASE_URL` in the shell overrides `.env`: `Remove-Item Env:DATABASE_URL`, open a new terminal, rerun preflight. |
| Check-in screen is a **[STUB]** | Skip it in the app. To show check-in, run `node scripts/demo.mjs`: its game-engine step does two check-ins and shows rank and quests (game-engine runs in memory mode). A repeat within the cooldown returns HTTP 409; restart game-engine to reset. |
| Any other stub (sign in, friends, leaderboard, quests, redemptions) | Say "no approved design yet, so it is a plain page" and move on. |

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
