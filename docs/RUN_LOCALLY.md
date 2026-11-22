# Run T-Quest locally

> Demo placeholder. No partnership, endorsement or real discount is implied. Sponsors, stores, offers and labels are placeholders. Rider data is synthetic; MBTA data is real. T-Quest is not deployed anywhere: it runs on your own machine.

The demo needs a PostgreSQL database with the TimescaleDB extension (we use a Tiger Data service). The repository does not contain our database or any credentials, so you bring your own.

## What was verified and what was not
- Verified (on the team laptop, against our Tiger Data service): everything from step 4 on, `node scripts/preflight.mjs`, and `node scripts/demo-up.mjs`.
- Not verified: creating a database from scratch with steps 2 and 3 on a machine other than ours, and the local Docker database in option B (Docker was not available when this was written).

## 1. Install
- Node.js 18 or newer and Python 3.11 or newer.
- From the repo root:
  ```powershell
  pip install -e data-platform -e insights-sponsors
  pip install -r game-engine/requirements.txt
  cd web; npm install; cd ..
  ```
  (The demo app in `client-bryan/demo` needs no install. `web/` is only used for the React port and for the recording tools.)

## 2. A database (pick one)
**A. Tiger Data (what we used).** Create a service in Tiger Cloud (Tiger Data) and copy its connection string.
**B. Local TimescaleDB (untested).** `docker compose -f data-platform/docker-compose.yml up -d`; the connection string is then `postgresql://postgres:postgres@localhost:5432/tquest`.

Copy `.env.example` to `.env` at the repo root and set `DATABASE_URL` (and `MBTA_API_KEY`, a free key from https://api-v3.mbta.com, which the collector needs). Never commit `.env`. If your shell already has a `DATABASE_URL`, clear it (PowerShell: `Remove-Item Env:DATABASE_URL`), because the shell value overrides `.env`.

## 3. Load the schema and data (from `data-platform/`, then `insights-sponsors/`)
```powershell
cd data-platform
$env:PYTHONPATH = "src"
python -m data_platform.migrate        # schema (migrations 0000-0015)
python -m data_platform.load_static    # MBTA routes, lines, stops, schedules (public MBTA API)
cd ../insights-sponsors
$env:PYTHONPATH = "src"
python scripts/load_seed.py            # demo sponsors, offers, nearby spots, labels, ranks (placeholders)
python -m ingest_content.run           # tourist content from Analyze Boston and Digital Commonwealth (open data, attribution stored)
```
For live trains, leave the collector running in its own terminal (`cd data-platform; python -m data_platform.collector`). Without it the map shows no moving trains.

## 4. Start the demo
```powershell
node scripts/preflight.mjs             # checks tools, env var names, database, collector freshness
node scripts/demo-up.mjs               # starts all services and the demo app
```
Open **http://localhost:4321**. Ctrl+C stops everything. It needs internet for map tiles, fonts and the public MBTA schedule API. Details, limits and troubleshooting: [DEMO.md](DEMO.md).

## No database? Watch the recording
`docs/demo/` is not committed. The captioned recording is linked from the project page. Screenshots are in [`docs/screenshots/`](screenshots/).

## Tests
`node --test tests/`, then `pytest -q` inside `data-platform/`, `insights-sponsors/`, `game-engine/` and `shared/`, and `npm test` in `web/`.
