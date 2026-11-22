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

## Update 2026-11-21 (real data run)
- MBTA key works. Real static data loaded (158 routes, 141 lines, 6774 stops). Collector: `python -m data_platform.collector` (Ctrl+C to stop). Benchmarks: `bench_real` and `demo_measure` write sections of docs/TIGER_DATA_RESULTS.md.
- Synthetic demo rows were cleaned out of the DB after the benchmark (they crowd the leaderboard test). Re-run `demo_measure` only for demos, then `--cleanup`.
- Real vehicles data accumulated so far is small (days of sporadic polling); run the collector longer for a stronger benchmark.

## Remaining
- Prompt 015 (Dockerfile and compose services) still queued.
- schema.sql is a concatenation of migrations, not a pg_dump (no pg_dump binary here).

## Update 2026-11-21 (migrations 0010, 0011)
- 0010: spot_categories, label_types, nearby_spots, spot_stop_links, spot_labels, view spot_labels_public, sponsors/stores.demo_placeholder. 0011: content_sources, content_items, stop_content, loading_facts. Both applied and verified on the live database; used by insights-sponsors. See DECISIONS D17 and docs/DATA_SOURCES.md.
- Pending: Dockerfile and compose (015). Roadmap checkboxes for 002-012 and 016 still read "DB-unverified" although the live run passed; tick them when convenient.

## Update (merge and cleanup pass)
- The shared `ranks` table now has 8 named ranks (game-engine). Anything that hard-codes the old 5-rank table is stale; the data-platform test no longer does.

## Update (final checks)
- Added `node scripts/demo.mjs` and docs/DEMO.md. Fixed: blank-title content rows (365 removed; the source was later dropped), 500s on malformed ids in Postgres mode, setup-me.mjs syntax error (#39). 198 insights-sponsors tests, 130 data-platform tests, 58 node tests pass.

## Update (issues #43/#44, sources)
- data-platform: `GET /me/travel` (routes/travel.py, tests/test_travel.py), migration 0012 (nearby_spots.fun_fact, fact_faves). insights-sponsors v0.7.0: /me/faves, Spot.fun_fact, stop-facts fallback. Historic-inventory source dropped (code and rows removed); ingestion User-Agent T-Quest-Hackathon/1.0. #43 and #44 stay open (unlocked_spots writer in game-engine, #64; along-line ordering). Counts: docs/DATA_SOURCES.md.
