# STATUS (2026-11-21, safe stop)

Sources: data-platform and insights-sponsors `.work/HANDOFF.md`, `node scripts/inbox.mjs`, open issues, git log. game-engine and both clients have no HANDOFF file; their rows come from git history and folders only.
Rule: no API-key / per-token billing. Everyone uses their own plan (AGENTS.md "Billing").

## Done per agent
- **data-platform (Eren):** prompts 001-014 built. Migrations 0000-0006 (core, rewards, realtime, aggregates, schema v0.1, insights aggregates), MBTA loader/ingest, read API, benchmark, `verify` runner, contract drafts in `data-platform/contracts-draft/`. Verified without a DB: 59 tests pass, 50 skipped. **No SQL has ever run on Postgres/TimescaleDB.**
- **insights-sponsors (Eren):** all 14 OpenAPI operations (draft v0.3.0) run on the in-memory backend with real Boston seed data; 149 tests pass. Postgres backend not built (014 partial, wip branch `wip/insights-sponsors-014`, commit ed294ec). Task 009 (LLM text) cancelled per billing rule.
- **game-engine (Tobi):** in-memory FastAPI service for all spec routes, plus rules for check-in, points, rank, redemption, badges, quests, friends, leaderboards, home line and delay compensation. `contracts/api/game-engine.yaml` is published. Shared badge slugs and MBTA route ids adopted. Does not use the `.work` queue yet.
- **client-bryan, client-isabella:** nothing built, by design. Folders hold README, AGENT.md and PLAN.md only. No sketches or Figma exist yet (#9).

## Remaining, priority order
1. Human #25: a database (Docker or Tiger Cloud `DATABASE_URL`) and an `MBTA_API_KEY`, then `python -m data_platform.verify`. Gates all DB proof and the Tiger Data prize numbers.
2. Human #27 and #26: publish `contracts-draft/` into `contracts/db` and the insights spec into `contracts/api/insights-sponsors.yaml`. data-platform's 016 first, so the contract has the right `home_line` name.
3. data-platform 016 (home_line 30-day rule, `checkins_30d`), then 015 (Dockerfile and compose services).
4. insights-sponsors 014, then 015-017 (Postgres backend, bus parity, latency numbers, demo smoke script).
5. Design intake (#9): sketches into `design/sketches/`, Figma links into `design/FIGMA_LINKS.md`. Clients build nothing until this exists.
6. game-engine: move to Postgres once schema is published; propose the check-in event schema in `contracts/events/`.

## Cross-agent blockers
- **Everyone is blocked on Eren:** #25, #27, #26 (all to:humans).
- **client-bryan** waits on #26 (insights spec) and #27 (data-platform spec). game-engine's spec is already published.
- **home_line name clash:** migration 0006 creates `checkins_28d`; #22 told insights-sponsors `checkins_30d`. Fixed by data-platform 016. Do 016 before publishing.
- **game-engine has no rank-4 badge**; insights-sponsors' seed has a rank-4 patch. Decide: drop it or ask for one (#5).
- **Attribution history (#23, #24):** commit 6732e8d has a co-author trailer, so `check-attribution` fails. Decide: rewrite history with a coordinated force-push, or allowlist it.

## Waiting on whom
| Issue | Waiting on |
|---|---|
| #25 database + MBTA key | Eren |
| #27 publish data-platform contracts | Eren (after 016) |
| #26 publish insights-sponsors spec | Eren |
| #23, #24 co-author trailer decision | Eren and team |
| #5 rank-4 badge | insights-sponsors and game-engine |
| #9 sketches / Figma | Bryan and Isabella |
| #10 client split | Isabella (reply to Bryan) |
| #1, #4, #6, #8, #22 | acked; close after #27 and #26 |
| #11 kickoff | everyone fills GitHub handle (Eren, Bryan, Isabella still TODO) |
| #14 "EVERYONE/AGENT Do before" | not a routed message; read and close or relabel |

## Top 5 when work resumes
1. Get a database: `tiger service create` (free plan) or Docker, put `DATABASE_URL` and `MBTA_API_KEY` in `.env` (#25).
2. Delete `data-platform/.work/STOP` and `insights-sponsors/.work/STOP`, start both duos; data-platform runs 015/016 first.
3. Run `python -m data_platform.verify`, fix whatever TimescaleDB rejects, then record compression ratio and CAGG latency.
4. Publish contracts (#27, #26) with `ALLOW_SHARED=1`, and `node ../scripts/done.mjs` the acked issues.
5. Bryan and Isabella drop sketches and Figma links, and reply on #10. Decide #23/#24 before judging.

Risks: no measured Tiger Data numbers yet; seed facts unsourced; auth is dev-mode only; cross-service demo data not yet consistent.
