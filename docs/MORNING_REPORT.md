# Morning report (overnight run, 2026-11-22)

**Shipped (all on main):**
- Phase 1: data-platform `GET /analytics/system` (read-only, public): vehicles per subway line now, active alerts and lines affected, vehicle reports per hour per line (from the `vehicles_route_5m` aggregate), hour-of-day activity, busiest and quietest hour and line. Contract 0.2.0, tests.
- Phase 2: Analytics tab, designed by the admin in `design/canvas/Analytics.dc.html` with a matching nav icon; four-column nav on every screen; web screen, tests (35 pass). Before/after screenshot diff: only the nav region changed.
- Phase 3: fresh screenshots of every screen in `docs/screenshots/` (8 files), README updated.
- Phase 4: `scripts/record-demo.mjs` now records the React app including Analytics, 2:04 long, captions checked against frames.
- Phase 5: README, PLAN, PITCH, DEMO, REHEARSAL, APP_SCOPE, DECISIONS (D19), web/README, `docs/DEVPOST_TEXT_SUGGESTIONS.md`.
- Phase 6: all checks green, claims audit updated, branch merged.

**Analytics contents:** live MBTA data (3 blocks, labeled "Live MBTA data"): right now, last hours, busiest and quietest. Demo block (labeled "demo rider data"): stops collected, home line, points, leaderboard place.

**Checks:** node tests 58, data-platform 155, insights 217 (3 skipped), game-engine 65 (17 database tests need `GE_TEST_DATABASE_URL`), shared 14, web 35, lint, type-check, build, `check-attribution`, `connect-check`, `e2e-prod` (48 checks), `preflight --running`, cold start: all pass. Secret scan: placeholders only; no personal emails in tracked files.

**YouTube (Phase 7):** uploaded to your channel, **Unlisted confirmed yes** (Studio list shows Unlisted). Link is in `docs/demo/links.txt` (gitignored). I uploaded a smaller VP9 re-encode (`docs/demo/tquest-demo-upload.webm`) because the browser tool caps files at 10 MB; the original is `docs/demo/tquest-demo.webm`.
**Devpost (Phase 8):** **saved yes, NOT submitted** (status still DRAFT, 4 of 5 steps). New gallery has the 8 new screenshots with captions (6 of 8 checked against the carousel); the 10 old images were removed; the video link is the new unlisted link and the embed loads. I did not touch text, team, tracks, prizes or tags. Screenshot of the state: `.work/devpost-final-state.jpg`.

**What the video does not show:** it was recorded around 2 AM, when the MBTA runs no trains, so "Ride there" shows "no train is scheduled at this hour" (the spoofed tap-out rejection is shown). Re-record after about 6 AM with `node scripts/record-demo.mjs` (restart `demo-up` first) to get a verified ride, then re-upload.

**You must do by hand:**
1. Watch the video; re-record in service hours for a verified ride if you want one; update the Devpost video link if you do.
2. Approve and apply `docs/DEVPOST_TEXT_SUGGESTIONS.md` (the story text on Devpost still describes the old demo app and does not mention Analytics).
3. Ask Isabella to review the Analytics tab design (admin-authored).
4. Re-run `bench_real` later for settled-chunk numbers (TODO: measure; response time of `/analytics/system` is also unmeasured and not quoted anywhere); then `node scripts/sync-docs.mjs`.
5. Click Submit on Devpost yourself.

**Noted:** the Devpost project now lists Tobi and Isabella as team members (added by someone else). Two extra browser tabs I opened (YouTube Studio, Devpost) are still open. Skipped: nothing.
