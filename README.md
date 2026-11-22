# T-Quest

> Working name. It can be renamed; nothing in the code depends on the name.

**Boston Hacks. Track: Transit Gamification. Subtrack: Best Use of Tiger Data.**

> **Demo disclaimer.** T-Quest is a hackathon prototype. Every sponsor, store, team, discount and label is a demo placeholder. No partnership, endorsement or real discount is implied. We are not pursuing real partnerships. Rider data is synthetic (flagged `is_synthetic`); stops, routes, schedules and live vehicles are real MBTA data.

T-Quest is a Pokemon-Go-style game layer over the MBTA, subway and bus. Riders check in at stops, collect them, track routes Strava-style, earn points, climb a travel rank and spend points on demo rewards (placeholder sponsors, see the disclaimer above). Every stop also shows what is nearby (food, coffee, shops), which riders can narrow by category and by verified community label. Tiger Data (Postgres + TimescaleDB) holds the relational profiles and the high-frequency MBTA streams in one database.

## The problem
Hundreds of thousands of people ride the MBTA every day. For residents it is a functional necessity: a predictable routine, platform waits, friction, and nothing gained when the T breaks. For tourists the T feels passive and disconnected from the city. The question we answer: how do we make the T ride something people look forward to? See [PITCH.md](PITCH.md) for our answers to the six track questions.

## Features

Status is derived from each agent's `.work/ROADMAP.md` and handoff notes. See [PLAN.md](PLAN.md) for the live checklist counts.

**Built**
- Tiger Data schema (migrations 0000-0011) applied to a live Tiger Cloud database: rider events, MBTA vehicles/predictions/alerts as hypertables, continuous aggregates, compression policies. `python -m data_platform.verify` passed on the live database.
- Real MBTA static data loaded (routes, lines, stops, schedules) and a standalone live collector for vehicles, predictions and alerts.
- Benchmark commands and measured results: [docs/TIGER_DATA_RESULTS.md](docs/TIGER_DATA_RESULTS.md). The real-data compression figures are TODO: measure.
- data-platform read API (FastAPI) and published contracts in `contracts/`.
- insights-sponsors service, OpenAPI v0.5.0 published in `contracts/api/`: stop facts, Freedom Trail, loading-screen facts, tourist content with attribution, demo offers and rank tiers, physical-reward catalog, **nearby spots with category and label filters** (with a hand-written demo fun fact per spot), faved facts (`/me/faves`) and a general-fact fallback for stops with no history. Its Postgres backend serves stops, offers, physical rewards, nearby spots and tourist content.
- Tourist content ingestion from official public APIs (Analyze Boston, Digital Commonwealth open-rights items, hand-written Freedom Trail facts), run once; counts in [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).
- game-engine service (Tobi): check-in, points, rank, redemption, badges, quests, friends, leaderboards, home line and delay compensation rules, with an in-memory mode and a Tiger Data (Postgres) store, OpenAPI published.

**In progress**
- Consent, place visits, personal analytics and recommendations in insights-sponsors still run on the in-memory backend with seed data; moving them to Postgres is planned, not done.
- Rider travel (`GET /me/travel`: miles per line, traveled segments) is built in data-platform from check-in events; with no real riders yet it returns zeros except for synthetic test riders.

**Planned**
- Rider-facing apps (client-bryan, client-isabella). They wait on sketches and Figma in `design/`; nobody invents UI.
- Community quests ("visit three local spots near stops") proposed to game-engine, delay and cancellation notifications.
- Opt-in tracking of other places visited, with explicit consent (the consent table and gate exist).

## Demo placeholders
The Boston Red Sox, Mint Julep (43 Brattle St, Cambridge, near Harvard) and Diesel Cafe (257 Elm St, Somerville, near Davis) appear only as demo placeholders, with just the facts we entered: name, address, nearby stop, category. Demo placeholder. No partnership, endorsement or real discount is implied. Real businesses carry no identity labels in the demo. Filtering by label is demonstrated on fictional "Sample ... (demo)" spots.

### Verified labels policy
In the demo no real business carries a label. In general, a label such as local/independent, woman-owned or veteran-owned would be shown for a business only if the business declared it itself or an official certification or directory lists it. We never infer a label from a name, photo, review or menu, and no model assigns labels. Pending labels are never returned and never match a filter.

## Architecture

```
 MBTA V3 API ──► collector ─┐
 MBTA static ──► loader ────┤
                            ▼
              Tiger Data (Postgres + TimescaleDB)  ◄── schema owned by data-platform
              hypertables, continuous aggregates, compression
                  ▲            ▲              ▲
        data-platform API  insights-sponsors  game-engine
                  ▲            ▲              ▲
                  └──── client-bryan / client-isabella (UI from design/ only)
```

Contract-first: OpenAPI files in `contracts/api/`, database contract in `contracts/db/`.

## Tiger Data usage
- `rider_events`, `vehicles`, `predictions`, `alerts` as hypertables.
- Continuous aggregates: leaderboards, home-line detection, per-line vehicle counts (`vehicles_route_5m`).
- Compression policies and `time_bucket` analytics, SQL-based recommendations.
- Measured numbers live only in [docs/TIGER_DATA_RESULTS.md](docs/TIGER_DATA_RESULTS.md) (copied into [PITCH.md](PITCH.md) automatically).

## Real data versus synthetic data
Stops, routes, schedules, live vehicles, predictions and alerts are **real** MBTA data. There are no users yet, so rider events used for benchmarks and demos are **synthetic** and flagged `is_synthetic`. Synthetic data is never presented as real users. Demo sponsors and sample businesses are labeled placeholders.

## Repo layout
| Path | What |
|---|---|
| `data-platform/` | schema, migrations, MBTA loader and collector, read API, benchmarks |
| `insights-sponsors/` | sponsors, offers, nearby spots, tourist content, analytics, recommendations |
| `game-engine/` | points, ranks, check-ins, redemption, quests (Tobi) |
| `client-bryan/`, `client-isabella/` | client apps, UI only from `design/` |
| `contracts/` | OpenAPI and database contracts |
| `design/` | sketches and Figma links (source of truth for UI) |
| `docs/` | brief, protocol, onboarding, results, data sources |
| `scripts/`, `tests/` | Node tooling for the team workflow |

## How to run
- Setup: [docs/ONBOARDING.md](docs/ONBOARDING.md).
- Collector (from `data-platform/`, needs `.env` with the database URL and MBTA key): `python -m data_platform.migrate`, `python -m data_platform.load_static`, `python -m data_platform.collector`.
- Tests: `node --test tests/` (repo tooling), `pytest -q` inside `data-platform/` and `insights-sponsors/`.
- Demo: `node scripts/demo.mjs` (see [docs/DEMO.md](docs/DEMO.md)).
- Docs refresh: `node scripts/sync-docs.mjs` (also the VS Code task "Sync docs").

## Team
| Person | Agents / area |
|---|---|
| Eren | data-platform, insights-sponsors |
| Tobi | game-engine |
| Bryan | client-bryan |
| Isabella | client-isabella |

## How the agents collaborate
Each person runs planner/builder agents inside their own folders. GitHub Issues is the only inter-agent channel. See [docs/PROTOCOL.md](docs/PROTOCOL.md), [docs/DUO.md](docs/DUO.md), [AGENTS.md](AGENTS.md) and [TEAM.md](TEAM.md).

## Data sources and credits
- **MBTA** V3 API and GTFS, under the MassDOT Developers License.
- **Analyze Boston** (data.boston.gov), Public Domain Dedication and License (PDDL).
- **Digital Commonwealth**: rights vary per item; only items with a clear no-known-restrictions or public-domain rights statement are used (metadata and link only).
- **Tiger Data** (Timescale) for Postgres + TimescaleDB.

Per-source terms, counts and the correction path are in [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).
