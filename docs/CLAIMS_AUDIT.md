# Claims audit

Checked 2026-11-21 against the repo as it is now: README.md, PLAN.md, PITCH.md, docs/DEMO.md, docs/APP_SCOPE.md. Verdicts: verified, unverified (softened or marked TODO), false (fixed).

| Claim | File | Evidence | Verdict |
|---|---|---|---|
| Nothing is deployed; no public URL | README, PLAN, PITCH, DEMO | text search: no deployed URL anywhere; "not deployed" stated | verified |
| Dockerfiles and Vercel are future, untested | README, DEMO | `future-hosting/README.md`; Dockerfiles never built | verified |
| Optional prod mode: signed tokens, exact CORS, rate limits, size limits, headers, fail-closed | README, PITCH | `shared/tests/`, `node scripts/e2e-prod.mjs` (47/47 checks passed) | verified |
| A restricted database role exists | README | no role in the database; the docs say it was removed | verified (documented as not built) |
| Migrations 0000-0015 applied on a live Tiger Cloud database | README, PLAN | `schema_migrations` read-only query | false (said 0000-0014 in one place); fixed |
| Real-data compression figures are "TODO: measure" | README | now measured in `docs/TIGER_DATA_RESULTS.md` | false (stale); fixed |
| "Real-data compression measurement" still in progress | README | measured 2026-11-21 | false (stale); fixed |
| Real data: 733,219 vehicles, 84.2x aggregate speedup, 15.3x / 24.3x chunk compression | README | copied from `docs/TIGER_DATA_RESULTS.md` | verified |
| Synthetic: 250,000 rider_events compress 5.9x | README | `docs/TIGER_DATA_RESULTS.md` (synthetic section, not re-measured) | verified (copied) |
| Hypertables: rider_events, points_ledger, vehicles, predictions, place_visits | README | migrations; `timescaledb_information.hypertables` | verified |
| Continuous aggregates and compression/retention policies as listed | README, PITCH | migrations 0003-0009; jobs query (compress after 1 day) | verified |
| "Hundreds of thousands of people ride the MBTA every day" | README, PITCH | no source in the repo | unverified; softened, TODO: verify |
| Delay and cancellation notifications | PITCH | not built (README lists as planned) | false as stated; marked planned |
| Compensation points when the home line has an outage | PITCH | rule in `game-engine/src/game_engine/delay.py` and `delay_job.py`; no screen | verified (clarified: rule only) |
| Community quests send riders to local businesses | PITCH | one demo quest in game-engine | unverified; marked proposed |
| Opt-in place tracking, revocable | PITCH | `insights-sponsors` consent and place-visit routes, in-memory backend | verified (clarified: not on Postgres) |
| Analytics hide groups under three riders; coordinates rounded | PITCH | `MIN_USERS = 3` in `analytics.py`; `COORDINATE_DECIMALS` in `routes/place_visits.py` | verified (in-memory backend) |
| Six built screens, stubs for sign in, check in, friends, leaderboard, quests, redemptions | README, PITCH, DEMO, APP_SCOPE | `web/src/screens/`, `docs/APP_SCOPE.md` | verified |
| Check-in works from the web stub | DEMO | `POST /checkins` with `place-pktrm` returned 201 in memory mode (fixed in game-engine, issue #78) | verified |
| game-engine runs in memory mode in the demo; nothing written to the database | DEMO | `/healthz` shows `"store":"memory"` | verified |
| Faves are written to the database and flagged is_demo | DEMO | migration 0015, `scripts/reset-demo.mjs` dry run | verified |
| Predictions by station id return nothing | DEMO | live query: no platform-to-station link in `stops` | verified |
| 8 named ranks, placeholder percentages | README, PITCH, DEMO | `ranks` table (8 rows), migration 0013 | verified |
| Sponsors, stores, offers and labels are demo placeholders; no partnership implied | all | `demo_placeholder` flags (migration 0014); disclaimer text in each file | verified |
| Real businesses carry no labels; Mint Julep's label is pending and never shown | README, PITCH, DEMO | live `/stops/place-harsq/nearby` returned Mint Julep with no labels | verified |
| Rider data is synthetic, not real users | all | `is_synthetic`; `rider_events` has 0 real rows | verified |
| Data sources: MBTA V3, Analyze Boston, Digital Commonwealth, hand-written Freedom Trail | README, PITCH | `docs/DATA_SOURCES.md` | verified |
| NFC or MHC/MACRIS features | all five files | text search: not mentioned | verified (absent) |
| No LLM or per-token billing in the product | README, PITCH | `scripts/billing.mjs`, tests/billing.test.mjs | verified |

Test counts are not quoted in these five files (they live in `.work/STATE.md`), so there is nothing to check.

Result: false 4 (all fixed), unverified 2 (softened or marked), everything else verified.

## Update 2026-11-22 (Analytics tab)
Re-checked README, PLAN, PITCH, DEMO, APP_SCOPE and REHEARSAL after adding the Analytics tab and switching the demo to the React app.

| Claim | File | Evidence | Verdict |
|---|---|---|---|
| Analytics has three live blocks computed from Tiger Data and one demo rider block, each labeled | README, PITCH, DEMO, APP_SCOPE | `data-platform/src/data_platform/routes/analytics.py`, `web/src/screens/screens.test.tsx` (labels), screenshot `docs/screenshots/07-analytics.png` | verified |
| The live blocks come from the `vehicles_route_5m` continuous aggregate and the live `vehicles` table | README, PITCH, DECISIONS | SQL in `routes/analytics.py` | verified |
| Every number on Analytics comes from an API response, none hard-coded | README, APP_SCOPE | `web/src/app/analytics.ts` builds strings from the response; test checks no placeholder text | verified |
| Analytics was designed by the admin and still needs Isabella's review | README, APP_SCOPE, DECISIONS | `design/canvas/Analytics.dc.html` header comment | verified |
| Adding the tab changed only the bottom nav on existing screens | APP_SCOPE | `scripts/visual-diff.py` before/after run (nothing above the nav differed except a moving train dot on Home) | verified |
| The hour-of-day view is thin until more days are collected | README, DEMO | endpoint returns `days` per hour; screen shows "up to N days" | verified |
| The demo app we record is the React app in `web/` | README, DEMO, REHEARSAL | `scripts/record-demo.mjs` targets port 5173 | verified |
| A verified ride appears in the video | DEMO | not when recorded overnight: no scheduled trains, so the video says so | unverified, documented in DEMO.md ("record during service hours") |
| Traveled shows miles from rides | DEMO | stays at zero until clients send `route_id` on check-ins (issue #81 delivered the API side) | verified, stated as zero until then |
| Response time of `/analytics/system` | (none quoted) | measured about a quarter of a second warm during development, not recorded in `docs/TIGER_DATA_RESULTS.md` | numbers removed from docs; TODO: measure |
| Earlier prototype `client-bryan/demo` is not the app we demo | README, DEMO | no Analytics there | verified |

Fixed in this pass: removed a response-time figure from DECISIONS and the Devpost suggestions (not in `docs/TIGER_DATA_RESULTS.md`), and removed pixel percentages from APP_SCOPE.

