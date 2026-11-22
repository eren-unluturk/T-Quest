# STATUS (updated 2026-11-21)

> Demo placeholder. No partnership, endorsement or real discount is implied. Every sponsor, store, team, discount and label is a demo placeholder; we are not pursuing real partnerships. Rider data is synthetic (`is_synthetic`); stops, routes, schedules and live vehicles are real MBTA data.

Sources: agents' `.work/HANDOFF.md` and `ROADMAP.md`, git history, open issues. Roadmap checkboxes can lag the real state. Live checklist counts are in [PLAN.md](../PLAN.md).

## Done per agent
- **data-platform (Eren):** migrations 0000-0012; `GET /me/travel` (miles per line, traveled segments, unlocked spots from `visit` events) built and tested; applied and verified on a live Tiger Cloud database (`python -m data_platform.verify` passed). Real MBTA static data loaded, live collector available, read API, benchmarks in [TIGER_DATA_RESULTS.md](TIGER_DATA_RESULTS.md). Real-data compression figures: TODO: measure.
- **insights-sponsors (Eren):** OpenAPI v0.5.0 published in `contracts/api/`. Postgres backend serves stops, offers, physical rewards, nearby spots (category and label filters) and tourist content. Content ingestion ran once from official public APIs (counts in [DATA_SOURCES.md](DATA_SOURCES.md)); faved facts, per-spot demo fun facts and a stop-fact fallback are built (contract v0.7.0). Demo placeholders only; labels demonstrated on fictional sample spots.
- **game-engine (Tobi):** service and rules for check-in, points, ranks, redemption, badges, quests, friends, leaderboards, home line and delay compensation, with an in-memory mode and a Postgres store. Its roadmap file is empty; see its README.
- **client-bryan, client-isabella:** no UI built; they wait on sketches and Figma in `design/`.

## Remaining
1. Consent, place visits, route analytics and recommendations in insights-sponsors still run in memory; moving them to Postgres is planned.
2. data-platform: Dockerfile and compose services (015); re-measure compression on settled chunks (TODO: measure).
3. Clients build from `design/` only.
4. Add a real public contact for corrections before any public launch (see DATA_SOURCES.md).
5. Open attribution-history decision (#23, #24).

## Open questions
See the open issues; `node scripts/inbox.mjs` lists them. #14 is not a routed message.
