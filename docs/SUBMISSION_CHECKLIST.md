# Submission checklist

"agent verified" means checked by an agent from the repo and by running the commands in this session. "you do this" needs a human.

## Done
- [x] Analytics tab built, tested and screenshotted; new video recorded (overnight, so no verified ride in it; re-record in the day if you want one) (agent verified)
- [x] Tests pass: `node --test tests/`, data-platform, insights-sponsors, game-engine, shared, web unit tests (agent verified)
- [x] Web lint, type-check and build pass (agent verified)
- [x] `node scripts/check-attribution.mjs` passes (agent verified)
- [x] `node scripts/connect-check.mjs` passes: every designed screen's endpoints work from a browser origin (agent verified)
- [x] `node scripts/e2e-prod.mjs` passes: optional production mode, throwaway secrets, no database (agent verified)
- [x] `node scripts/preflight.mjs --running` passes with the demo started by `node scripts/demo-up.mjs` from a cold start (agent verified)
- [x] Live database: migrations 0000-0015 applied; collector newest vehicle row was seconds old during the check (agent verified)
- [x] Demo rows are marked and removable: `node scripts/reset-demo.mjs` shows a dry-run count first (agent verified; the delete itself was not run)
- [x] Secret scan of tracked files: no real credentials found; `.env` is gitignored and untracked (agent verified)
- [x] Demo footer, disclaimer and data credits are in the web app and docs (agent verified in code and docs; look at the screen yourself too)
- [x] Public hosting documented as future work, untested files in `future-hosting/` (agent verified)

## You do this
- [ ] Re-run `bench_real` after the collector has run longer and replace the stale real-data numbers in `docs/TIGER_DATA_RESULTS.md` with settled-chunk figures, then `node scripts/sync-docs.mjs` (you do this)
- [ ] Stop the collector only when you decide to (you do this)
- [ ] Watch the new video, then upload it to YouTube (unlisted) if the agent did not, and put the link on Devpost (you do this; see docs/DEVPOST_TEXT_SUGGESTIONS.md)
- [ ] Approve and apply the Devpost text suggestions in `docs/DEVPOST_TEXT_SUGGESTIONS.md` (you do this)
- [ ] Ask Isabella to review the Analytics tab design (you do this)
- [ ] Rehearse the 3-minute demo end to end with preflight green (you do this)
- [ ] Confirm every teammate has pulled main and can run `node scripts/demo-up.mjs` (you do this)
- [ ] Get the check-in screen design from Bryan and Isabella (currently a stub), or decide to demo without it (you do this)
- [ ] Choose a license (TODO for you)
- [ ] Final read of README, PLAN and PITCH for any claim that is not true (you do this)
- [ ] Look at the running app once to confirm the demo disclaimer and data credits are visible on every screen (you do this)
- [ ] Repo link and submission form fields (you do this)
- [ ] Add a real public contact for corrections if the project ever goes public (see `docs/DATA_SOURCES.md`) (you do this)
