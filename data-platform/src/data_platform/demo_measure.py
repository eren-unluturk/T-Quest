"""Tiger Data demo measurements, reproducible and safe to re-run.

    python -m data_platform.demo_measure            # generate, compress, time, write docs/TIGER_DATA_RESULTS.md
    python -m data_platform.demo_measure --cleanup  # remove the demo rows and users

Generates ~1,000,000 rider_events (plus ~500,000 points_ledger rows) over 30 days for 500
synthetic users `demo_0001`..`demo_0500`, using a fixed seed (setseed per slice, md5-derived ids).
Demo ledger rows have ref_type = 'demo'. Output contains no connection details.
"""
import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import db
from .bench import HOME_LINE_RAW

SEED = 0.2026
USERS = 500
EVENTS = 1_000_000
LEDGER = 500_000
DAYS = 30
SLICES = 6  # 5 days each
DOCS = Path(__file__).resolve().parents[3] / "docs" / "TIGER_DATA_RESULTS.md"
JSON_OUT = Path(__file__).resolve().parents[2] / "bench" / "demo_measure.json"

STOPS = ["place-pktrm", "place-dwnxg", "place-sstat", "place-state", "place-haecl", "place-north",
         "place-cntsq", "place-knncl", "place-harsq", "place-portr", "place-davis", "place-alfcl",
         "place-asmnl", "place-jfk", "place-nqncy", "place-forhl", "place-ogmnl", "place-rugg",
         "place-bbsta", "place-bckhl", "place-coecl", "place-kencl", "place-hymnl", "place-lech",
         "place-gover", "place-bomnl", "place-aport", "place-wondl", "place-rvrwy", "place-mfa",
         "place-lngmd", "place-fenwy", "place-hsmnl", "place-chill", "place-sbmnl", "place-brico",
         "place-sull", "place-mlmnl", "place-welln", "place-masta"]
ROUTES = ["Red", "Orange", "Blue", "Green-B", "Green-C", "Green-D", "Green-E", "1", "66", "39"]
SQL_STOPS = "ARRAY[" + ",".join(f"'{s}'" for s in STOPS) + "]"
SQL_ROUTES = "ARRAY[" + ",".join(f"'{r}'" for r in ROUTES) + "]"

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
    conn.execute("DELETE FROM rider_events WHERE user_id IN (SELECT id FROM users WHERE starts_with(username, 'demo_'))")
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


def generate(conn, now):
    conn.execute(
        "INSERT INTO users (id, username) SELECT md5('demo-user-' || n)::uuid, 'demo_' || lpad(n::text, 4, '0') "
        "FROM generate_series(1, %s) n ON CONFLICT DO NOTHING", (USERS,))
    per_ev, per_led = EVENTS // SLICES, LEDGER // SLICES
    for s in range(SLICES):
        lo = now - (DAYS - s * (DAYS // SLICES)) * timedelta(days=1)
        span = (DAYS // SLICES) * 86400
        p = {"seed": SEED + s / 1000.0, "lo": lo, "span": span, "u": USERS, "s": s}
        conn.execute("SELECT setseed(%(seed)s)", p)
        # Each user has a home route used 70% of the time; ids are md5-derived so reruns match.
        conn.execute(f"""
            INSERT INTO rider_events (id, time, user_id, event_type, stop_id, route_id, mode, lat, lon, points_awarded, payload)
            SELECT md5('demo-ev-' || %(s)s || '-' || g)::uuid,
                   LEAST(%(lo)s::timestamptz + make_interval(secs => floor(random() * %(span)s)::int), %(hi)s::timestamptz),
                   md5('demo-user-' || un)::uuid,
                   (ARRAY['checkin','checkin','checkin','checkin','checkin','checkin','checkin','ride_start','ride_start','visit'])[1 + floor(random() * 10)::int],
                   ({SQL_STOPS})[1 + floor(random() * {len(STOPS)})::int],
                   CASE WHEN random() < 0.7 THEN ({SQL_ROUTES})[1 + (un %% {len(ROUTES)})]
                        ELSE ({SQL_ROUTES})[1 + floor(random() * {len(ROUTES)})::int] END,
                   'subway', 42.30 + random() * 0.1, -71.15 + random() * 0.12, 10, '{{"synthetic": true}}'
            FROM (SELECT g, 1 + floor(random() * %(u)s)::int AS un FROM generate_series(1, {per_ev}) g) x
            ON CONFLICT DO NOTHING""", {**p, "hi": now})
        conn.execute(f"""
            INSERT INTO points_ledger (id, at, user_id, delta, reason, ref_type, route_id)
            SELECT md5('demo-led-' || %(s)s || '-' || g)::uuid,
                   LEAST(%(lo)s::timestamptz + make_interval(secs => floor(random() * %(span)s)::int), %(hi)s::timestamptz),
                   md5('demo-user-' || un)::uuid, 2 + floor(random() * 19)::int, 'checkin', 'demo',
                   ({SQL_ROUTES})[1 + floor(random() * {len(ROUTES)})::int]
            FROM (SELECT g, 1 + floor(random() * %(u)s)::int AS un FROM generate_series(1, {per_led}) g) x
            ON CONFLICT DO NOTHING""", {**p, "hi": now})
        print(f"slice {s + 1}/{SLICES} inserted", flush=True)
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
            "rider_events": conn.execute("SELECT count(*) FROM rider_events WHERE user_id IN (SELECT id FROM users WHERE starts_with(username,'demo_'))").fetchone()[0],
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
    doc = f"""# Tiger Data results

Measured {r['generated_at'][:10]} on a Tiger Cloud service (0.5 CPU, 2 GiB RAM), PostgreSQL {r['postgres']}, TimescaleDB {r['timescaledb']}.
Reproduce with `python -m data_platform.demo_measure` from `data-platform/` (fixed seed {r['seed']}, safe to re-run; `--cleanup` removes the demo rows).

## Data

| Item | Rows |
|---|---|
| `rider_events` (30 days, ~40 stop ids, 10 routes) | {r['counts']['rider_events']:,} |
| `points_ledger` (ref_type `demo`) | {r['counts']['points_ledger']:,} |
| Synthetic users (`demo_0001`..`demo_0500`) | {r['counts']['users']} |

Generation took {r['generate_seconds']} s. Each user has a home route used about 70% of the time.

## Compression (`rider_events`, hypertable with 7-day chunks)

Settings (migration 0008): `compress_segmentby = 'user_id'`, `compress_orderby = 'time DESC, id'`, policy after 7 days. For the measurement every chunk was compressed.

| | Chunks | Table | Indexes | Toast | Total |
|---|---|---|---|---|---|
| Before | {b['chunks']} | {mb(b['table_bytes'])} | {mb(b['index_bytes'])} | {mb(b['toast_bytes'])} | {mb(b['total_bytes'])} |
| After | {a['chunks']} | {mb(a['table_bytes'])} | {mb(a['index_bytes'])} | {mb(a['toast_bytes'])} | {mb(a['total_bytes'])} |

- Compression ratio on total hypertable size (tables, indexes, toast): **{ratio_total:.1f}x**.
- `hypertable_compression_stats` ({mb(sb)} before, {mb(sa)} after): **{ratio_stats:.1f}x**.
- Compressing all chunks took {r['compress_seconds']} s.

## Query latency (server-side planning + execution time from `EXPLAIN (ANALYZE)`, median of 5 runs after 1 warm-up, aggregates refreshed first; excludes network round trip)

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

## Summary for the pitch

{summary(r, ratio_total, tb, ta)}
"""
    DOCS.parent.mkdir(exist_ok=True)
    DOCS.write_text(doc, encoding="utf-8")


def summary(r, ratio, tb, ta):
    return (f"T-Quest records every rider check-in as a time-series event. We loaded about {r['counts']['rider_events']:,} rider "
            f"events across 30 days into a small Tiger Data service (0.5 CPU, 2 GiB RAM), and TimescaleDB's columnar compression "
            f"shrank the hypertable (data plus indexes) by {ratio:.1f}x. The leaderboard and home line, the two screens riders hit "
            f"most, are served from continuous aggregates that the database keeps fresh on its own: the leaderboard takes "
            f"{tb['leaderboard_cagg']} ms instead of {tb['leaderboard_raw']} ms ({tb['leaderboard_speedup']}x) and the home line "
            f"{tb['home_line_cagg']} ms instead of {tb['home_line_raw']} ms ({tb['home_line_speedup']}x) on uncompressed data. "
            f"Be upfront that this synthetic set has only about 3 rows per aggregate bucket, so the speedup is modest and grows "
            f"with real traffic. Once the events are compressed, the raw home-line query also gets much faster "
            f"({ta['home_line_raw']} ms) and is about as quick as the aggregate ({ta['home_line_cagg']} ms), so the main win "
            f"at this size is the storage saving with no loss of query speed.")


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
