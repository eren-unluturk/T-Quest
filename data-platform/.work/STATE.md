# STATE (builder)

- Role: BUILDER
- Startup: read AGENTS.md, PROJECT_BRIEF, AGENT.md, DECISIONS, ROADMAP, BUILDER.md. Doctor run.
- Doctor: attribution check FAILS on history commit 6732e8d1f5 (teammate Co-authored-by trailer). Fixing needs a history rewrite, which is forbidden for the builder. Planner/humans should decide.
- Queue: empty (no prompts in .work/queue/). ROADMAP has no items.
- Current prompt: none
- Last result: waiting for planner to add prompts

# STATE (planner)

- Cycle 1 (2026-11-21 ~12:55): queued 001-009, wrote ROADMAP, acked #4 #6 #8 #11, raised attribution-history issue to humans.
- Waiting on: builder reports for 001+. Eren to publish contracts-draft/ after 004.
- Reviewed reports: 001, 002, 003 (code OK; all DB checks unverified, no docker/postgres, #25).
- Cycle 2: acked #22; amended 006 (checkins_28d, user_stop_daily, stop_popularity_hourly); queued 010 (schema v0.1 for #22 + user_rank fix).
- Cycle 3: verified 004 (drafts ready); reviewed 005 (bug: compress orderby lacks unique-index cols) -> queued 011; decided badges/ranks/users owned by game-engine (added to 010); opened #27 to:humans to publish drafts.
- Cycle 4: reviewed 006 (built from pre-amendment prompt) -> queued 012 for user_stop_daily/stop_popularity_hourly and checkins_28d. 009 already covers CAGG-vs-raw timing.
- Cycle 5: reviewed 007 (OK; live run needs key + DB, asked on #25).
- Billing rule received: no per-token API billing; audited data-platform (clean), recorded in ROADMAP. Never queue LLM/API-key work.
- Cycle 6: reviewed 008 (OK, DB-unverified).
- Next: review 009-012; then, if a DB exists, queue the verification prompt.
