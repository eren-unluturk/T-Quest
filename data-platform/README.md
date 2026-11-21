# data-platform

Owner: Eren. Python 3.11+ FastAPI service (see DECISIONS.md).

Owns the Tiger Data (Postgres + TimescaleDB) schema and everything that feeds it: migrations, MBTA ingestion workers, continuous aggregates, compression, retention, docker-compose, and the read API for stops/lines/live data.

See AGENT.md for charter, owned paths and definition of done.

## Layout
- `src/data_platform/` - service code (`app.py`, `db.py`, `migrate.py`)
- `migrations/` - ordered SQL migrations (`NNNN_name.sql`)
- `tests/` - tests

## Quickstart (local TimescaleDB)
```powershell
copy .env.example .env
docker compose up -d
pip install -e .[dev]
python -m data_platform.migrate
uvicorn data_platform.app:app
```
Then open http://localhost:8000/health.

Run tests with `pytest -q`. Tests that need a database skip when it is unreachable.

## Migrations
- Files in `migrations/` named `NNNN_*.sql` apply in lexical order, each in its own transaction, and are recorded in `schema_migrations`. Re-running applies nothing new.
- A file whose first line is `-- migrate:no-transaction` runs in autocommit mode. Use it for continuous aggregates and their policies, which cannot run inside a transaction block.
- If an applied file's checksum changes, the runner warns but does not fail. Add a new migration instead of editing an applied one.

## Tiger Cloud
1. Create a service (see DECISIONS.md D12).
2. Set `DATABASE_URL` in `.env` to the service URL, with `sslmode=require`:
   `postgres://tsdbadmin:<password>@<host>:<port>/tsdb?sslmode=require`
3. Run the same command: `python -m data_platform.migrate`.

## Load MBTA data
Set `MBTA_API_KEY` in `.env` (free key from api-v3.mbta.com; without a key the API allows only about 20 requests/min, which is not enough for the static load).

```powershell
python -m data_platform.load_static          # routes, stops, route_stops (upsert, safe to re-run)
python -m data_platform.ingest --once        # one cycle: vehicles, predictions, alerts
python -m data_platform.ingest --interval 15 # poll every 15 seconds until stopped
```
Predictions are polled for subway and light-rail routes only (the MBTA API requires a route filter), so run `load_static` first. A failed cycle is logged and the loop continues.


## Benchmark (demo numbers)
```powershell
python -m data_platform.bench                 # 7 days, 2000 users, 600 vehicles polled every 15 s
python -m data_platform.bench --synthetic-days 1 --users 100 --vehicles 50   # quick run
python -m data_platform.bench --cleanup       # remove all synthetic rows and users
```
Writes `bench/RESULTS.md` and `bench/results.json`: compression ratio for `vehicles` and `predictions`, and median latency of the leaderboard and home-line continuous aggregates against the same queries on raw tables. The default run inserts about 24 million vehicle rows; use the smaller flags for a quick check. If `TIGER_DATABASE_URL` is set the run is repeated there (migrate that database first) and results get a second column.

## Verify everything
One command runs the full check against whatever `DATABASE_URL` points at (connect, migrate twice, seed, MBTA load and one ingest cycle if `MBTA_API_KEY` is set, the test suite, a small benchmark with cleanup, TimescaleDB introspection). It writes `verify/VERIFY.md` and `verify/verify.json` (hostnames, passwords and IPs are redacted) and exits non-zero if any step failed.

Local docker:
```powershell
docker compose up -d
copy .env.example .env      # set MBTA_API_KEY to also test ingestion
pip install -e .[dev]
python -m data_platform.verify
```
Tiger Cloud: set `DATABASE_URL` in `.env` to the service URL (with `sslmode=require`), then run `python -m data_platform.verify`. Flags: `--skip-mbta`, `--skip-bench`, `--bench-days 2`.
