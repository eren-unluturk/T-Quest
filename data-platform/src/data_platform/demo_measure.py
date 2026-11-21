"""Tiger Data demo measurements, reproducible and safe to re-run.

    python -m data_platform.demo_measure            # generate, compress, time, write docs/TIGER_DATA_RESULTS.md
    python -m data_platform.demo_measure --cleanup  # remove the demo rows and users

Generates ~250,000 SYNTHETIC rider_events (is_synthetic = true; plus ~125,000 points_ledger rows) over
30 days for 500 synthetic users `demo_0001`..`demo_0500`, using a fixed seed. Riders are anchored to the
real MBTA data loaded by `python -m data_platform.load_static`: real routes, the real stops served by
each route and direction, and the hour-of-day distribution of scheduled trips (route_schedule_hourly).
Demo ledger rows have ref_type = 'demo'. Output contains no connection details.
"""
import argparse
import json
import random
import uuid
from zoneinfo import ZoneInfo
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import db, docs_util
from .bench import HOME_LINE_RAW

SEED = 0.2026
USERS = 500
EVENTS = 250_000
LEDGER = 125_000
DAYS = 30
DOCS = Path(__file__).resolve().parents[3] / "docs" / "TIGER_DATA_RESULTS.md"
JSON_OUT = Path(__file__).resolve().parents[2] / "bench" / "demo_measure.json"


LEADERBOARD_RAW_30D = """
    WITH t AS (
        SELECT user_id, sum(delta) FILTER (WHERE delta > 0) AS pts FROM points_ledger
        WHERE at >= time_bucket('1 day', now() - interval '30 days') GROUP BY user_id)
    SELECT (rank() OVER (ORDER BY t.pts DESC NULLS LAST))::int, t.user_id, u.username, t.pts
    FROM t JOIN users u ON u.id = t.user_id ORDER BY 1, u.username LIMIT 50"""
LEADERBOARD_CAGG = "SELECT * FROM leaderboard('global', 'month', NULL, NULL, 50)"
HOME_LINE_CAGG = "SELECT * FROM home_line"


def cleanup(conn):
    conn.execute("SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0")
    # Decompress first so re-runs start from clean, uncompressed chunks (no partially compressed leftovers).
    conn.execute("SELECT decompress_chunk(c, if_compressed => true) FROM show_chunks('rider_events') c").fetchall()
    conn.execute("DELETE FROM rider_events WHERE is_synthetic OR user_id IN (SELECT id FROM users WHERE starts_with(username, 'demo_'))")
    conn.execute("ALTER TABLE points_ledger DISABLE TRIGGER points_ledger_no_mutation")
    try:
        conn.execute("DELETE FROM points_ledger WHERE ref_type = 'demo'")
    finally:
        conn.execute("ALTER TABLE points_ledger ENABLE TRIGGER points_ledger_no_mutation")
    conn.execute("DELETE FROM users WHERE starts_with(username, 'demo_')")
    for t in ("rider_events", "points_ledger"):
        conn.execute(f"VACUUM (FULL, ANALYZE) {t}")
    for c in ("leaderboard_daily", "user_route_daily", "home_line_weekly"):
        conn.execute(f"CALL refresh_continuous_aggregate('{c}', NULL, NULL)")
    for (m,) in conn.execute("SELECT format('%I.%I', materialization_hypertable_schema, materialization_hypertable_name) "
                             "FROM timescaledb_information.continuous_aggregates").fetchall():
        conn.execute(f"VACUUM (FULL, ANALYZE) {m}")


def _load_anchors(conn):
    """Real routes, route stops and scheduled hourly trips from the database."""
    routes = {r[0]: r[1] for r in conn.execute("SELECT id, mode FROM routes").fetchall()}
    stops = {}
    for rid, did, sid, lat, lon in conn.execute(
            "SELECT rs.route_id, rs.direction_id, s.id, s.lat, s.lon FROM route_stops rs JOIN stops s ON s.id = rs.stop_id"):
        stops.setdefault((rid, did), []).append((sid, lat, lon))
    sched = {}
    for rid, did, hour, trips in conn.execute("SELECT route_id, direction_id, hour_of_day, trips FROM route_schedule_hourly"):
        sched.setdefault(rid, {}).setdefault(did, {})[hour] = trips
    usable = sorted(r for r in sched if r in routes and any((r, d) in stops for d in sched[r]))
    if not usable:
        raise SystemExit("no real MBTA static data: run `python -m data_platform.load_static` first")
    return routes, stops, sched, usable


def generate(conn, now):
    conn.execute(
        "INSERT INTO users (id, username) SELECT md5('demo-user-' || n)::uuid, 'demo_' || lpad(n::text, 4, '0') "
        "FROM generate_series(1, %s) n ON CONFLICT DO NOTHING", (USERS,))
    routes, stops, sched, usable = _load_anchors(conn)
    rng = random.Random(SEED)
    tz = ZoneInfo("America/New_York")
    weights = [sum(sum(h.values()) for h in sched[r].values()) for r in usable]
    users = [uuid.UUID(hex=__import__("hashlib").md5(f"demo-user-{n}".encode()).hexdigest()) for n in range(1, USERS + 1)]
    home = [rng.choices(usable, weights)[0] for _ in users]  # each user's home route, used ~70% of the time
    types = ["checkin"] * 7 + ["ride_start"] * 2 + ["visit"]
    day0 = (now.astimezone(tz) - timedelta(days=DAYS)).replace(hour=0, minute=0, second=0, microsecond=0)

    def pick_time(route):
        dirs = [d for d in sched[route] if (route, d) in stops]
        d = rng.choice(dirs)
        hours = sched[route][d]
        hour = rng.choices(list(hours), list(hours.values()))[0]
        day = day0 + timedelta(days=rng.randrange(DAYS))
        t = (day + timedelta(hours=hour, minutes=rng.randrange(60), seconds=rng.randrange(60))).astimezone(timezone.utc)
        return d, min(t, now - timedelta(minutes=1))

    def uid(kind, i):
        return uuid.uuid5(uuid.NAMESPACE_URL, f"tquest-demo-{kind}-{SEED}-{i}")

    with conn.cursor().copy(
            "COPY rider_events (id, time, user_id, event_type, stop_id, route_id, mode, lat, lon, points_awarded, payload, is_synthetic) FROM STDIN") as cp:
        for i in range(EVENTS):
            u = rng.randrange(USERS)
            route = home[u] if rng.random() < 0.7 else rng.choices(usable, weights)[0]
            d, t = pick_time(route)
            sid, lat, lon = rng.choice(stops[(route, d)])
            cp.write_row((uid("ev", i), t, users[u], rng.choice(types), sid, route, routes[route], lat, lon, 10,
                          '{"synthetic": true}', True))
    print(f"rider_events inserted: {EVENTS}", flush=True)
    with conn.cursor().copy(
            "COPY points_ledger (id, at, user_id, delta, reason, ref_type, route_id) FROM STDIN") as cp:
        for i in range(LEDGER):
            u = rng.randrange(USERS)
            route = home[u] if rng.random() < 0.7 else rng.choices(usable, weights)[0]
            _, t = pick_time(route)
            cp.write_row((uid("led", i), t, users[u], 2 + rng.randrange(19), "checkin", "demo", route))
    print(f"points_ledger inserted: {LEDGER}", flush=True)
    conn.execute("ANALYZE rider_events")
    conn.execute("ANALYZE points_ledger")


def sizes(conn):
    r = conn.execute("""SELECT table_bytes, index_bytes, toast_bytes, total_bytes
                        FROM hypertable_detailed_size('rider_events')""").fetchone()
    chunks = conn.execute("SELECT count(*) FROM show_chunks('rider_events')").fetchone()[0]
    return {"chunks": chunks, "table_bytes": r[0], "index_bytes": r[1], "toast_bytes": r[2], "total_bytes": r[3]}


def _server_ms(conn, sql):
    """Server-side planning + execution time, so the client network round trip is excluded."""
    plan = conn.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + sql).fetchone()[0][0]
    return plan["Planning Time"] + plan["Execution Time"]


def median_ms(conn, sql, runs=5):
    _server_ms(conn, sql)  # warm-up, not counted
    ts = [_server_ms(conn, sql) for _ in range(runs)]
    return round(statistics.median(ts), 2), [round(t, 2) for t in ts]


def timings(conn):
    out = {}
    for name, sql in (("leaderboard_cagg", LEADERBOARD_CAGG), ("leaderboard_raw", LEADERBOARD_RAW_30D),
                      ("home_line_cagg", HOME_LINE_CAGG), ("home_line_raw", HOME_LINE_RAW)):
        out[name] = median_ms(conn, sql)[0]
    out["leaderboard_speedup"] = round(out["leaderboard_raw"] / out["leaderboard_cagg"], 1)
    out["home_line_speedup"] = round(out["home_line_raw"] / out["home_line_cagg"], 1)
    return out


def mb(b):
    return f"{b / 1024 / 1024:.1f} MB"


def run():
    with db.connect(autocommit=True) as conn:
        print("cleanup of previous demo rows", flush=True)
        # decompress is not needed: deletes on compressed chunks are supported (TimescaleDB 2.11+)
        cleanup(conn)
        now = datetime.now(timezone.utc)
        t0 = time.time()
        generate(conn, now)
        gen_s = round(time.time() - t0)
        counts = {
            "rider_events": conn.execute("SELECT count(*) FROM rider_events WHERE is_synthetic").fetchone()[0],
            "points_ledger": conn.execute("SELECT count(*) FROM points_ledger WHERE ref_type='demo'").fetchone()[0],
            "users": conn.execute("SELECT count(*) FROM users WHERE starts_with(username,'demo_')").fetchone()[0],
        }
        # compress anything left from an earlier run so "before" is truly uncompressed
        before = sizes(conn)
        print("refreshing aggregates", flush=True)
        for c in ("leaderboard_daily", "user_route_daily", "home_line_weekly"):
            conn.execute(f"CALL refresh_continuous_aggregate('{c}', NULL, NULL)")
        t_before = timings(conn)
        print("compressing", flush=True)
        t0 = time.time()
        conn.execute("SELECT compress_chunk(c, if_not_compressed => true) FROM show_chunks('rider_events') c").fetchall()
        comp_s = round(time.time() - t0, 1)
        after = sizes(conn)
        stats = conn.execute("""SELECT before_compression_total_bytes, after_compression_total_bytes
                                FROM hypertable_compression_stats('rider_events')""").fetchone()
        t_after = timings(conn)
        pg = conn.execute("SHOW server_version").fetchone()[0].split(" ")[0]
        ts = conn.execute("SELECT extversion FROM pg_extension WHERE extname='timescaledb'").fetchone()[0]
        res = {"generated_at": now.isoformat(), "postgres": pg, "timescaledb": ts, "seed": SEED, "counts": counts,
               "generate_seconds": gen_s, "compress_seconds": comp_s, "before": before, "after": after,
               "compression_stats_bytes": list(stats), "timings_before_compression": t_before,
               "timings_after_compression": t_after}
    JSON_OUT.parent.mkdir(exist_ok=True)
    JSON_OUT.write_text(json.dumps(res, indent=2))
    write_doc(res)
    print(json.dumps({k: res[k] for k in ("counts", "before", "after", "timings_before_compression",
                                           "timings_after_compression")}, indent=1))


def write_doc(r):
    b, a = r["before"], r["after"]
    ratio_total = b["total_bytes"] / a["total_bytes"]
    sb, sa = r["compression_stats_bytes"]
    ratio_stats = sb / sa if sa else 0
    tb, ta = r["timings_before_compression"], r["timings_after_compression"]
    doc = f"""Source of every number in this section: SYNTHETIC rider events (`rider_events.is_synthetic = true`) generated by `data_platform.demo_measure`, not real riders. The stops, routes and scheduled hours they are anchored to are real MBTA static data.

Measured {r['generated_at'][:10]} on a Tiger Cloud service (0.5 CPU, 2 GiB RAM), PostgreSQL {r['postgres']}, TimescaleDB {r['timescaledb']}.
Reproduce with `python -m data_platform.demo_measure` from `data-platform/` (fixed seed {r['seed']}, safe to re-run; `--cleanup` removes the demo rows).

### Data

| Item | Rows |
|---|---|
| `rider_events` (30 days, real MBTA stops/routes, schedule-weighted hours) | {r['counts']['rider_events']:,} |
| `points_ledger` (ref_type `demo`) | {r['counts']['points_ledger']:,} |
| Synthetic users (`demo_0001`..`demo_0500`) | {r['counts']['users']} |

Generation took {r['generate_seconds']} s. Each user has a home route used about 70% of the time.

### Compression (`rider_events`, hypertable with 7-day chunks)

Settings (migration 0008): `compress_segmentby = 'user_id'`, `compress_orderby = 'time DESC, id'`, policy after 7 days. For the measurement every chunk was compressed.

| | Chunks | Table | Indexes | Toast | Total |
|---|---|---|---|---|---|
| Before | {b['chunks']} | {mb(b['table_bytes'])} | {mb(b['index_bytes'])} | {mb(b['toast_bytes'])} | {mb(b['total_bytes'])} |
| After | {a['chunks']} | {mb(a['table_bytes'])} | {mb(a['index_bytes'])} | {mb(a['toast_bytes'])} | {mb(a['total_bytes'])} |

- Compression ratio on total hypertable size (tables, indexes, toast): **{ratio_total:.1f}x**.
- `hypertable_compression_stats` ({mb(sb)} before, {mb(sa)} after): **{ratio_stats:.1f}x**.
- Compressing all chunks took {r['compress_seconds']} s.

### Query latency (server-side planning + execution time from `EXPLAIN (ANALYZE)`, median of 5 runs after 1 warm-up, aggregates refreshed first; excludes network round trip)

| Query | Continuous aggregate (ms) | Raw table (ms) | Speedup |
|---|---|---|---|
| Leaderboard, global, last 30 days, top 50 (uncompressed raw) | {tb['leaderboard_cagg']} | {tb['leaderboard_raw']} | {tb['leaderboard_speedup']}x |
| Home line for every user (uncompressed raw) | {tb['home_line_cagg']} | {tb['home_line_raw']} | {tb['home_line_speedup']}x |
| Leaderboard (after compressing `rider_events`) | {ta['leaderboard_cagg']} | {ta['leaderboard_raw']} | {ta['leaderboard_speedup']}x |
| Home line for every user (after compressing `rider_events`) | {ta['home_line_cagg']} | {ta['home_line_raw']} | {ta['home_line_speedup']}x |

The leaderboard reads `points_ledger` (not compressed), so its raw timing does not change with `rider_events` compression. The home-line raw query reads `rider_events`.

### Exact queries

Leaderboard, continuous aggregate (`leaderboard_daily`):

```sql
{LEADERBOARD_CAGG}
```

Leaderboard, raw table:

```sql
{LEADERBOARD_RAW_30D.strip()}
```

Home line, continuous aggregate (`user_route_daily` behind the `home_line` view, 30 days, at least 5 rides, ties to the most recent line):

```sql
{HOME_LINE_CAGG}
```

Home line, raw table:

```sql
{HOME_LINE_RAW.strip()}
```

### Summary for the pitch

{summary(r, ratio_total, tb, ta)}
"""
    docs_util.upsert_section(DOCS, "synthetic", "Synthetic rider events", doc)


def summary(r, ratio, tb, ta):
    return (f"{r['counts']['rider_events']:,} synthetic rider events (anchored to real MBTA stops, routes and schedule hours) "
            f"compress {ratio:.1f}x on total hypertable size. Query timings are reported as measured, with no claim of a "
            f"continuous-aggregate win: on this small, single-run dataset on a 0.5 CPU service, the aggregate was "
            f"{tb['leaderboard_speedup']}x (leaderboard) and {tb['home_line_speedup']}x (home line) relative to raw before compression, "
            f"and {ta['leaderboard_speedup']}x and {ta['home_line_speedup']}x after. Timings vary run to run on a shared service; "
            f"treat speedups near or below 1x as noise at this size. The real-data section has the continuous-aggregate comparison on live MBTA data.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cleanup", action="store_true")
    args = ap.parse_args()
    if args.cleanup:
        with db.connect(autocommit=True) as c:
            cleanup(c)
        print("demo rows removed")
    else:
        run()
    sys.exit(0)
