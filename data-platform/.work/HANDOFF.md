# HANDOFF: data-platform builder, 2026-11-21 (second unattended run)

## Done
- Database reachable (Tiger Cloud, PostgreSQL 18.7, TimescaleDB 2.32.1). Migrations 0000-0008 apply cleanly and idempotently; dev seed applied; `python -m data_platform.verify` PASS; pytest 119 passed, 0 skipped.
- Fixed two test bugs (a `%` placeholder and an invalid redemption code) and made `bench --cleanup` work on compressed chunks.
- Migration 0007 (home_line 30-day window, tie-break, override) works on the live DB. Migration 0008 adds rider_events compression.
- Tiger Data numbers: docs/TIGER_DATA_RESULTS.md (about 1M events, 9.5x compression, aggregate speedups 1.9x leaderboard and 5.0x home line on uncompressed data). Re-run: `python -m data_platform.demo_measure`.
- Contracts in contracts/db/ updated for 0008.

## Gotchas
- A stale DATABASE_URL (no password) exists in the Windows/shell environment and overrides ../.env (dotenv does not override). Remove it or run with `unset DATABASE_URL`.
- Do not leave demo rows in the DB: 500 demo users crowd the leaderboard test (top 50). Run `python -m data_platform.demo_measure --cleanup` after demos.

## Remaining
- MBTA ingestion not run (MBTA_API_KEY missing). Add the key, then `python -m data_platform.verify`.
- Prompt 015 (Dockerfile and compose services) still queued.
- schema.sql is a concatenation of migrations, not a pg_dump (no pg_dump binary here).
