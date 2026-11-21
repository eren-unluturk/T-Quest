---
id: 013
title: DB-free SQL syntax check for every migration
status: ready
depends_on: [012]
---
## Goal
No migration has ever run against Postgres (no DB on this machine, issue #25). Catch syntax errors now by parsing every migration and seed file with the real Postgres parser (libpg_query) inside the test suite, so it runs without a database.

## Context
- `migrations/*.sql`, `seeds/*.sql`
- `src/data_platform/migrate.py` (`split_statements()`, the no-transaction marker)
- `tests/test_split_statements.py`

## Steps
1. Add `pglast` (Python bindings to libpg_query, the actual Postgres parser) to dev deps and `pip install` it. If no wheel installs on this Windows machine/Python version, try the previous major version; if neither installs, mark this prompt `blocked` with the pip error in the report.
2. `tests/test_sql_syntax.py`: for every file in `migrations/` and `seeds/`, `pglast.parser.parse_sql(text)` must succeed. Parametrize by file name so failures name the file. pglast parses TimescaleDB calls fine (they are ordinary function calls and `WITH (...)` options).
3. Also assert that `split_statements()` on each no-transaction file yields statements that each parse on their own, and that the count equals the number of top-level statements pglast reports.
4. Fix any syntax errors found in migrations or seeds. Because no database has applied any migration, edit files in place. List every fix in the report.
5. Add a pure-text check in the same test file: every `create_hypertable`, `add_compression_policy`, `add_retention_policy`, `add_continuous_aggregate_policy` call has `if_not_exists => TRUE`, and every `CREATE TABLE|INDEX|VIEW|MATERIALIZED VIEW` uses `IF NOT EXISTS` or `OR REPLACE` (idempotency rule). Fix violations.

## Acceptance criteria
- `pytest -q tests/test_sql_syntax.py` passes with no database.
- Every migration and seed file is covered.
- Report lists any fixes made.

## Tests to run
`pytest -q`

## Out of scope
Semantic checks that need a live DB (types, FKs, TimescaleDB restrictions).

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
