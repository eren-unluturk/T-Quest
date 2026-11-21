# Tiger Data results

Measured 2026-11-21 on a Tiger Cloud service (0.5 CPU, 2 GiB RAM), PostgreSQL 18.7, TimescaleDB 2.32.1.
Reproduce with `python -m data_platform.demo_measure` from `data-platform/` (fixed seed 0.2026, safe to re-run; `--cleanup` removes the demo rows).

## Data

| Item | Rows |
|---|---|
| `rider_events` (30 days, ~40 stop ids, 10 routes) | 999,996 |
| `points_ledger` (ref_type `demo`) | 499,998 |
| Synthetic users (`demo_0001`..`demo_0500`) | 500 |

Generation took 73 s. Each user has a home route used about 70% of the time.

## Compression (`rider_events`, hypertable with 7-day chunks)

Settings (migration 0008): `compress_segmentby = 'user_id'`, `compress_orderby = 'time DESC, id'`, policy after 7 days. For the measurement every chunk was compressed.

| | Chunks | Table | Indexes | Toast | Total |
|---|---|---|---|---|---|
| Before | 6 | 155.5 MB | 256.3 MB | 0.1 MB | 411.9 MB |
| After | 6 | 4.7 MB | 0.6 MB | 38.1 MB | 43.3 MB |

- Compression ratio on total hypertable size (tables, indexes, toast): **9.5x**.
- `hypertable_compression_stats` (411.9 MB before, 43.0 MB after): **9.6x**.
- Compressing all chunks took 4.9 s.

## Query latency (server-side planning + execution time from `EXPLAIN (ANALYZE)`, median of 5 runs after 1 warm-up, aggregates refreshed first; excludes network round trip)

| Query | Continuous aggregate (ms) | Raw table (ms) | Speedup |
|---|---|---|---|
| Leaderboard, global, last 30 days, top 50 (uncompressed raw) | 210.44 | 395.1 | 1.9x |
| Home line for every user (uncompressed raw) | 215.74 | 1069.72 | 5.0x |
| Leaderboard (after compressing `rider_events`) | 191.41 | 418.3 | 2.2x |
| Home line for every user (after compressing `rider_events`) | 204.37 | 174.75 | 0.9x |

The leaderboard reads `points_ledger` (not compressed), so its raw timing does not change with `rider_events` compression. The home-line raw query reads `rider_events`.

### Exact queries

Leaderboard, continuous aggregate (`leaderboard_daily`):

```sql
SELECT * FROM leaderboard('global', 'month', NULL, NULL, 50)
```

Leaderboard, raw table:

```sql
WITH t AS (
        SELECT user_id, sum(delta) FILTER (WHERE delta > 0) AS pts FROM points_ledger
        WHERE at >= time_bucket('1 day', now() - interval '30 days') GROUP BY user_id)
    SELECT (rank() OVER (ORDER BY t.pts DESC NULLS LAST))::int, t.user_id, u.username, t.pts
    FROM t JOIN users u ON u.id = t.user_id ORDER BY 1, u.username LIMIT 50
```

Home line, continuous aggregate (`user_route_daily` behind the `home_line` view, 30 days, at least 5 rides, ties to the most recent line):

```sql
SELECT * FROM home_line
```

Home line, raw table:

```sql
WITH recent AS (
        SELECT user_id, route_id, count(*) AS checkins_30d, max(time) AS last_ride FROM rider_events
        WHERE event_type IN ('checkin', 'ride_start') AND route_id IS NOT NULL
          AND time >= time_bucket('1 day', now() - interval '30 days') GROUP BY user_id, route_id),
    ranked AS (SELECT *, row_number() OVER (PARTITION BY user_id
                                            ORDER BY checkins_30d DESC, last_ride DESC, route_id) AS rn
               FROM recent)
    SELECT user_id, route_id, checkins_30d FROM ranked WHERE rn = 1 AND checkins_30d >= 5
```

## Summary for the pitch

T-Quest records every rider check-in as a time-series event. We loaded about 999,996 rider events across 30 days into a small Tiger Data service (0.5 CPU, 2 GiB RAM), and TimescaleDB's columnar compression shrank the hypertable (data plus indexes) by 9.5x. The leaderboard and home line, the two screens riders hit most, are served from continuous aggregates that the database keeps fresh on its own: the leaderboard takes 210.44 ms instead of 395.1 ms (1.9x) and the home line 215.74 ms instead of 1069.72 ms (5.0x) on uncompressed data. Be upfront that this synthetic set has only about 3 rows per aggregate bucket, so the speedup is modest and grows with real traffic. Once the events are compressed, the raw home-line query also gets much faster (174.75 ms) and is about as quick as the aggregate (204.37 ms), so the main win at this size is the storage saving with no loss of query speed.

The demo rows were removed after the measurement so they do not skew the shared test data; re-run the command above to regenerate them.
