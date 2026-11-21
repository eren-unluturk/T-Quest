# data-platform

Owner: Eren. Python 3.11+ FastAPI service (see DECISIONS.md).

Own the Tiger Data (Postgres + TimescaleDB) schema and everything that feeds it: migrations, MBTA ingestion workers, continuous aggregates, compression, retention, docker-compose, and the read API for stops/lines/live data.

See AGENT.md for charter, owned paths and definition of done.

- `src/` - service code
- `tests/` - tests
