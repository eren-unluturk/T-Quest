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
- Next: review 006+; when a DB exists, queue a verification prompt re-running all DB tests.
