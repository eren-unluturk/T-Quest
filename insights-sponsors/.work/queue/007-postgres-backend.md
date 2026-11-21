---
id: 007
title: Postgres (Tiger Data) repository backend
status: blocked
issue: 1
depends_on: [006]
---
BLOCKED: waiting on the data-platform v0 schema in `../contracts/db/` (issue #1) and the column request sent to data-platform. The planner will flip this to `ready` and fill in exact table names when the schema lands.

## Goal
`PostgresRepository` implementing the same `Repository` protocol against the shared Tiger Data database, selected with `data_backend=postgres`. Analytics and recommendations run the `.sql` files from 006. A seed loader pushes our catalog and content JSON into the data-platform-owned tables.

## Context
- `../contracts/db/` (when published)
- `src/insights_sponsors/repo/base.py`, `repo/memory.py`, `sql/*.sql`
- `../.env.example` (`DATABASE_URL`)

## Steps
(Planner completes these when unblocked: the psycopg3 pool, a query per method, `scripts/load_seed.py` (upsert), an integration test marked `@pytest.mark.db` and skipped without `DATABASE_URL`, and a latency measurement of the aggregate queries for the demo.)

## Acceptance criteria
- Same route tests pass with `data_backend=postgres` against a seeded DB.
- Aggregate query latency recorded in the report.

## Tests to run
- `pytest -q` and `pytest -q -m db` with `DATABASE_URL` set

## Out of scope
- Schema changes (request them from data-platform by issue).

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
