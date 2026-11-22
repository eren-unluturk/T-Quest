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
- Tiger Data schema (migrations 0000-0011) applied to a live Tiger Cloud database: rider events, MBTA vehicles and predictions as hypertables (alerts are plain tables), continuous aggregates, compression policies. `python -m data_platform.verify` passed on the live database.
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

## Tech stack

**Overview.** T-Quest is a monorepo of three Python FastAPI services (data-platform, insights-sponsors, game-engine) that all read and write one Tiger Data database (Postgres + TimescaleDB). data-platform owns the schema and the MBTA ingestion; the other two services own game logic and tourist/sponsor content. The services publish OpenAPI contracts that the front end is built against. There are no LLM or AI API calls anywhere in the code; recommendations and analytics are plain SQL and Python rules.

```
 MBTA V3 API (live) ──► collector (vehicles, predictions, alerts) ─┐
 MBTA V3 / GTFS (static) ──► load_static (routes, stops, schedules) ┤
 Analyze Boston, Digital Commonwealth ──► ingest_content ──────────┤
 hand-written Freedom Trail + fun facts ────────────────────────────┤
                                                                    ▼
                  Tiger Data (Postgres + TimescaleDB)  ◄── schema owned by data-platform
                  hypertables · continuous aggregates · compression
                        ▲                ▲                 ▲
                 data-platform     insights-sponsors   game-engine
                 (read API :8001)  (:8002)             (:8003)
                        ▲                ▲                 ▲
                        └── OpenAPI contracts (contracts/api/) ──┘
                                         ▲
                              web app / clients (UI from design/ only)
```

### Layers

| Layer | Technology | What it does here | Where in the repo |
|---|---|---|---|
| Database | Tiger Data (Tiger Cloud): PostgreSQL + TimescaleDB | Single store for profiles, rewards, content and the high-volume MBTA streams. Measured on PostgreSQL 18.7, TimescaleDB 2.32.1, 0.5 CPU, 2 GiB | `data-platform/migrations/` (0000-0012), [docs/TIGER_DATA_RESULTS.md](docs/TIGER_DATA_RESULTS.md) |
| Local database | Docker Compose, image `timescale/timescaledb:latest-pg16` | Local TimescaleDB for development | `data-platform/docker-compose.yml` |
| Schema and migrations | Plain SQL files, ordered runner (`python -m data_platform.migrate`) | Creates tables, hypertables, aggregates and policies; idempotent | `data-platform/migrations/`, `data-platform/src/data_platform/migrate.py` |
| Database contract | Markdown + concatenated SQL | What other agents may rely on | `contracts/db/SCHEMA.md`, `contracts/db/schema.sql` |
| Services | Python 3.11+, FastAPI, uvicorn | data-platform read API (stops, routes, lines, vehicles, predictions, alerts, travel), insights-sponsors (content, offers, nearby spots, consent, analytics, recommendations), game-engine (check-ins, points, ranks, badges, quests, friends, redemption) | `data-platform/`, `insights-sponsors/`, `game-engine/` |
| DB access | psycopg 3 (binary); psycopg-pool in insights-sponsors | Direct SQL, no ORM | each service's `pyproject.toml` / `requirements.txt` |
| Models and config | pydantic v2, pydantic-settings (insights-sponsors), python-dotenv (data-platform) | Request/response models, env-based settings | `insights-sponsors/src/insights_sponsors/models.py`, `config.py` |
| HTTP client | httpx | Calls the MBTA V3 API | `data-platform/src/data_platform/mbta.py` |
| API contracts | OpenAPI (YAML), contract-first | The interface the front end and other services build against | `contracts/api/{data-platform,insights-sponsors,game-engine}.yaml` |
| Collector / ingestion | Python modules run with `python -m` | `load_static` loads routes, stops, schedules; `collector` stores live vehicles, predictions and alerts; `ingest_content` loads open tourist content (about 1 s between requests) | `data-platform/src/data_platform/{load_static,collector,ingest}.py`, `insights-sponsors/ingest_content/` |
| Benchmarks | Python scripts using `EXPLAIN (ANALYZE)` | Compression ratio and aggregate-vs-raw timings | `data-platform/src/data_platform/{bench,bench_real,demo_measure,verify}.py` |
| Auth (on main) | Demo bearer token: the token is the sandbox username. game-engine also accepts an `X-Store-Key` header for store verification | Identifies demo users. Not real authentication | `game-engine/src/game_engine/app.py`, `insights-sponsors/src/insights_sponsors/auth.py` |
| CORS (on main) | FastAPI `CORSMiddleware` | data-platform allows any origin for GET; insights-sponsors is configurable by env; game-engine sets its own allowed headers | each service's `app.py` / `main.py` |
| Hardening (in progress) | HMAC-signed short-lived tokens, rate limits, body-size limit, security headers | Prepared on branch `demo-deploy`, not merged to main | branch `demo-deploy`: `shared/tquest_auth.py`, `shared/tquest_http.py` |
| Web app (in progress) | React 18, TypeScript, Vite, Vitest, ESLint | Front end ported from the approved design canvas. Local `web/` folder, not committed yet | `web/package.json` (uncommitted), `design/canvas/` |
| Python tests | pytest, pytest-asyncio (data-platform), openapi-spec-validator, pyyaml, pglast (SQL syntax checks) | Unit, contract-conformance and migration-syntax tests; `db`-marked tests need a database | `*/tests/` |
| Repo tooling tests | Node's built-in test runner (`node --test`) | Tests hooks, ownership guard, billing safety, attribution, docs sync | `tests/*.test.mjs` |
| Linting | None configured for Python. ESLint only in the uncommitted `web/` | | |
| Docker (services) | Dockerfiles for the three services | Prepared on branch `demo-deploy`, not merged to main | branch `demo-deploy`: `*/Dockerfile` |
| Hosting | Vercel for the front end; a container or Python host for the three backends | Described in [docs/FRONTEND_INTEGRATION.md](docs/FRONTEND_INTEGRATION.md). **Prepared, not deployed.** | `docs/FRONTEND_INTEGRATION.md` |
| CI | GitHub Actions: one workflow, `route-issues` (labels agent-message issues) | No build or test CI | `.github/workflows/route-issues.yml` |

### How we use Tiger Data

All of this exists in `data-platform/migrations/`.
- **Hypertables:** `rider_events` (0001), `points_ledger` (0001), `vehicles` and `predictions` (0003), `place_visits` (0005). `alerts` and `alert_entities` are ordinary tables, not hypertables.
- **Continuous aggregates, each with a refresh policy:** `leaderboard_daily`, `home_line_weekly`, `personal_stats_daily` (0004); `user_stop_daily`, `user_stop_hourly` (0006); `user_route_daily` (0007, the 30-day home-line rule); `vehicles_route_5m` (0009, vehicle reports per line per 5 minutes).
- **Compression policies:** `vehicles` and `predictions` after 1 day (0003), `rider_events` after 7 days with `compress_segmentby = 'user_id'` (0008).
- **Retention policies:** `vehicles` and `predictions` 30 days (0003), `place_visits` 90 days (0005).
- **`time_bucket` analytics:** the aggregates above, the benchmark scripts and `insights-sponsors/sql/analytics_me.sql`, `analytics_boston.sql`.
- **SQL recommendations:** drafts in `insights-sponsors/sql/recs_*.sql`. Today recommendations are served by the in-memory backend with seed data; running them on Postgres is planned, not done.
- **Measured numbers** (all from [docs/TIGER_DATA_RESULTS.md](docs/TIGER_DATA_RESULTS.md), never edited by hand):
  - Synthetic data: 250,000 `rider_events` compress 5.9x on total hypertable size (96.0 MB to 16.2 MB). Aggregate-vs-raw speedups on that small set range from 0.8x to 1.6x, reported as measured with no claim of a win.
  - Real data: on live MBTA `vehicles` (274,565 rows), the `vehicles_route_5m` aggregate ran 8.41x faster than the raw table before forced compression. Real-data compression ratio: TODO: measure (settled chunks).

### Data sources

| Source | What it provides | Attribution and terms |
|---|---|---|
| MBTA V3 API and GTFS | Routes, lines, stops, schedules (static); vehicles, predictions, alerts (live). Real data | MassDOT Developers License |
| Analyze Boston (data.boston.gov, CKAN API) | Boston Landmarks Commission landmarks and historic districts, linked to nearby stops in SQL | Public Domain Dedication and License (PDDL); attribution stored with each item |
| Digital Commonwealth (official JSON API) | Historic item metadata and links, only items whose rights statement is no-known-restrictions or public domain. No coordinates, so not linked to stops | Rights per item |
| Hand-written content | Freedom Trail sites and loading-screen fun facts, written by the team, marked `needs_verify` | Ours; a human must verify before publishing |

**Real versus synthetic.** Stops, routes, schedules, live vehicles, predictions and alerts are real MBTA data. There are no real users yet, so rider events used for benchmarks and demos are synthetic and flagged `is_synthetic` (migration 0009); they are never presented as real riders. Per-source counts and the correction path: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

### Developer workflow
- **Monorepo.** One folder per agent (see Repo layout). Each person writes only in their own folders; `team.json` defines folders and per-path ownership.
- **Message board.** GitHub Issues is the only channel between agents. Labels: `to:*`, `from:*`, `type:request|question|blocker|contract-change|handoff|done`, `priority:blocker`, `status:acked`. The `route-issues` workflow applies labels from the issue form. Protocol: [docs/PROTOCOL.md](docs/PROTOCOL.md).
- **Planner/builder agents.** Each agent folder has a `.work/` directory (roadmap, prompt queue, reports, handoff). A planner session writes prompts and handles GitHub; a builder session implements them. See [docs/DUO.md](docs/DUO.md).
- **Git hooks (`.githooks/`).** `pre-commit` is the ownership guard (`ALLOW_SHARED=1` overrides it); `commit-msg` and `pre-push` strip or reject attribution lines.
- **Node scripts (`scripts/`):**
  - `setup-me.mjs`: write your identity and set up hooks. `doctor.mjs`: setup checklist.
  - `inbox.mjs`, `watch-inbox.mjs`: show your open issues. `send.mjs`, `ack.mjs`, `done.mjs`: create, acknowledge and close messages.
  - `duo.mjs`: launch a planner or builder session. `planner-guard.mjs`: keeps planners inside `.work/`.
  - `seed-work.mjs`, `seed-issues.mjs`, `setup-labels.mjs`, `sync-claude-config.mjs`: one-time and sync helpers.
  - `sync-docs.mjs`: refresh the generated blocks in PLAN.md and PITCH.md. `check-attribution.mjs`: audit history, files and issues.
  - `billing.mjs`: billing-safety helpers used by `doctor.mjs` and `duo.mjs`. `demo.mjs`: start the services and print a tour. `connect-check.mjs`: front-end wiring check.
- **Slash commands** (`.claude-template/commands/`, copied into every agent folder): `/inbox`, `/send`, `/ack`, `/done`, `/handoff`, `/docs-refresh`.

### Project status by layer

| Layer | Built | In progress | Planned |
|---|---|---|---|
| Database | Migrations 0000-0012 on a live Tiger Cloud service; `verify` passed; aggregates, compression and retention policies | Real-data compression measurement | |
| Ingestion | MBTA static load, live collector, tourist content ingestion (run once) | | |
| data-platform API | Read API for stops, routes, lines, vehicles, predictions, alerts, travel; contract published | | |
| insights-sponsors | Content, offers, rank tiers, physical-reward catalog, nearby spots, tourist content on Postgres; faves endpoints; contract published | Consent, place visits, analytics, recommendations still on the in-memory backend | Move those to Postgres; community quests |
| game-engine | Rules, in-memory and Postgres stores, contract published | Shared auth and hardening (`demo-deploy` branch) | Delay and cancellation notifications |
| Front end | Approved design canvas in `design/canvas/` | `web/` React + Vite port (uncommitted) | Hosting on Vercel and a backend container host |

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
- Front-end wiring: [docs/FRONTEND_INTEGRATION.md](docs/FRONTEND_INTEGRATION.md) and `node scripts/connect-check.mjs`.
- Demo: `node scripts/demo.mjs` (see [docs/DEMO.md](docs/DEMO.md)).
- Docs refresh: `node scripts/sync-docs.mjs` (also the VS Code task "Sync docs").

## Team
| Person | Agents / area |
|---|---|
| Eren | data-platform, insights-sponsors |
| Tobi | game-engine |
| Bryan | client-bryan |
| Isabella | client-isabella |

## Credits
MBTA data under the MassDOT Developers License. Analyze Boston under the PDDL. Digital Commonwealth items under their own stated rights. Postgres + TimescaleDB on Tiger Data (Timescale). Details per source: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).
