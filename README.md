# T-Quest

> Working name. It can be renamed; nothing in the code depends on the name.

**Boston Hacks. Track: Transit Gamification. Subtrack: Best Use of Tiger Data.**

T-Quest is a Pokemon-Go-style game layer over the MBTA, subway and bus. Riders check in at stops, collect them, track routes Strava-style, earn points, climb a travel rank and spend points on local rewards. Every stop also shows what is nearby (food, coffee, shops), which riders can narrow by category and by verified community label. Tiger Data (Postgres + TimescaleDB) holds the relational profiles and the high-frequency MBTA streams in one database.

## The problem
Hundreds of thousands of people ride the MBTA every day. For residents it is a functional necessity: a predictable routine, platform waits, friction, and nothing gained when the T breaks. For tourists the T feels passive and disconnected from the city. The question we answer: how do we make the T ride something people look forward to? See [PITCH.md](PITCH.md) for our answers to the six track questions.

## Features

Status is derived from each agent's `.work/ROADMAP.md` and handoff notes. See [PLAN.md](PLAN.md) for the live checklist counts.

**Built**
- Tiger Data schema (migrations 0000-0009) applied to a live Tiger Cloud database: rider events, MBTA vehicles/predictions/alerts as hypertables, continuous aggregates, compression policies. `python -m data_platform.verify` passed on the live database.
- Real MBTA static data loaded (routes, lines, stops, schedules) and a standalone live collector for vehicles, predictions and alerts.
- Benchmark commands and measured results: [docs/TIGER_DATA_RESULTS.md](docs/TIGER_DATA_RESULTS.md).
- data-platform read API (FastAPI) and published contracts in `contracts/`.
- insights-sponsors service: stop facts, Freedom Trail, loading-screen facts, offers, physical-reward catalog, consent, place visits, personal and Boston analytics, deterministic recommendations. Runs on an in-memory backend with seed data (OpenAPI draft v0.3.0).
- game-engine service (Tobi): check-in, points, rank, redemption, badges, quests, friends, leaderboards, home line and delay compensation rules, on an in-memory backend, with its OpenAPI published.

**In progress**
- insights-sponsors Postgres backend: sponsors, offers, physical rewards, and the **nearby-spots feature** (every stop lists nearby spots; filter by category and by verified identity label; sponsors get native highlighted placement, other spots are free listings).
- Tourist content ingestion from open sources (Analyze Boston, MassGIS/MACRIS, Digital Commonwealth), with attribution stored per record.

**Planned**
- Rider-facing apps (client-bryan, client-isabella). They wait on sketches and Figma in `design/`; nobody invents UI.
- game-engine on Postgres, community quests ("visit three local spots near stops"), delay and cancellation notifications.
- Opt-in tracking of other places visited, with explicit consent (the consent table and gate exist).

### Verified labels policy
A label such as local/independent, woman-owned or veteran-owned is shown for a business only if the business declared it itself or an official certification or directory lists it. We never infer a label from a name, photo, review or menu, and no model assigns labels. Pending labels are never returned and never match a filter.

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
- **MassGIS / Massachusetts Historical Commission**, MACRIS historic inventory data.
- **Digital Commonwealth**: rights vary per item; only items with a clear public-domain or open-reuse rights statement are used.
- **Tiger Data** (Timescale) for Postgres + TimescaleDB.

Per-source terms and the business-correction path will be in `docs/DATA_SOURCES.md`.
