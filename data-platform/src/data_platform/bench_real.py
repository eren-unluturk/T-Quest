"""Benchmark on REAL MBTA data collected by `data_platform.collector`.

    python -m data_platform.bench_real

Reports row counts, hypertable size before/after compressing every chunk, compression ratio, and
timings (median of 5 after 1 warm-up, server-side planning + execution from EXPLAIN ANALYZE) of the
`vehicles_route_5m` continuous aggregate vs the same query on the raw `vehicles` table.
Appends/replaces the "Real MBTA data" section of docs/TIGER_DATA_RESULTS.md. Run it with the
collector stopped. Contains no connection details.
"""
import json
import sys
from datetime import datetime, timezone

from . import db, docs_util
from .demo_measure import DOCS, median_ms, mb

WINDOW = "3 days"
CAGG_SQL = f"""
    SELECT l.id AS line_id, c.bucket, sum(c.reports) AS reports
    FROM vehicles_route_5m c JOIN routes r ON r.id = c.route_id JOIN lines l ON l.id = r.line_id
    WHERE c.bucket >= now() - interval '{WINDOW}'
    GROUP BY l.id, c.bucket ORDER BY l.id, c.bucket"""
RAW_SQL = f"""
    SELECT l.id AS line_id, time_bucket('5 minutes', v.time) AS bucket, count(*) AS reports
    FROM vehicles v JOIN routes r ON r.id = v.route_id JOIN lines l ON l.id = r.line_id
    WHERE v.time >= now() - interval '{WINDOW}'
    GROUP BY l.id, time_bucket('5 minutes', v.time) ORDER BY l.id, bucket"""
SIZE_SQL = "SELECT table_bytes, index_bytes, toast_bytes, total_bytes FROM hypertable_detailed_size(%s::regclass)"


def size(conn, table):
    t, i, o, total = conn.execute(SIZE_SQL, (table,)).fetchone()
    return {"table": t or 0, "index": i or 0, "toast": o or 0, "total": total or 0}


def timings(conn):
    c, raw = median_ms(conn, CAGG_SQL)[0], median_ms(conn, RAW_SQL)[0]
    return {"cagg_ms": c, "raw_ms": raw, "speedup": round(raw / c, 2) if c else None}


def run() -> dict:
    with db.connect(autocommit=True) as conn:
        conn.execute("SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0")
        conn.execute("CALL refresh_continuous_aggregate('vehicles_route_5m', NULL, NULL)")
        counts = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                  for t in ("vehicles", "predictions", "alerts", "alert_entities")}
        span = conn.execute("SELECT min(time), max(time) FROM vehicles").fetchone()
        agg_rows = conn.execute("SELECT count(*) FROM vehicles_route_5m").fetchone()[0]
        res = {"generated_at": datetime.now(timezone.utc).isoformat(), "counts": counts,
               "vehicles_span": [str(span[0]), str(span[1])], "cagg_rows": agg_rows}
        res["size_before"] = {t: size(conn, t) for t in ("vehicles", "predictions")}
        res["timings_before_compression"] = timings(conn)
        for t in ("vehicles", "predictions"):
            conn.execute("SELECT compress_chunk(c, if_not_compressed => true) FROM show_chunks(%s::regclass) c", (t,)).fetchall()
        res["size_after"] = {t: size(conn, t) for t in ("vehicles", "predictions")}
        res["compression_stats"] = {
            t: [int(x) for x in conn.execute(
                "SELECT coalesce(sum(before_compression_total_bytes),0), coalesce(sum(after_compression_total_bytes),0) "
                "FROM hypertable_compression_stats(%s::regclass)", (t,)).fetchone()]
            for t in ("vehicles", "predictions")}
        res["timings_after_compression"] = timings(conn)
        res["timescaledb"] = conn.execute("SELECT extversion FROM pg_extension WHERE extname='timescaledb'").fetchone()[0]
    write_doc(res)
    return res


def write_doc(r) -> None:
    c = r["counts"]
    rows = []
    for t in ("vehicles", "predictions"):
        b, a = r["size_before"][t]["total"], r["size_after"][t]["total"]
        sb, sa = r["compression_stats"][t]
        rows.append(f"| `{t}` | {mb(b)} | {mb(a)} | {b / a:.1f}x | {sb / sa:.1f}x |" if a and sa else f"| `{t}` | {mb(b)} | {mb(a)} | n/a | n/a |")
    tb, ta = r["timings_before_compression"], r["timings_after_compression"]
    body = f"""Source of every number in this section: REAL data from the MBTA V3 API (`/vehicles`, `/predictions`, `/alerts`, subway, light rail and bus), collected by `python -m data_platform.collector` into Tiger Data. No synthetic rows are involved. Measured {r['generated_at'][:10]} on a Tiger Cloud service (0.5 CPU, 2 GiB RAM), TimescaleDB {r['timescaledb']}. Reproduce with `python -m data_platform.bench_real` (collector stopped).

### Data (source: MBTA V3 live feed)

| Table | Rows |
|---|---|
| `vehicles` (positions, {r['vehicles_span'][0][:16]} to {r['vehicles_span'][1][:16]} UTC) | {c['vehicles']:,} |
| `predictions` | {c['predictions']:,} |
| `alerts` | {c['alerts']:,} |
| `alert_entities` | {c['alert_entities']:,} |
| `vehicles_route_5m` aggregate buckets | {r['cagg_rows']:,} |

### Compression (source: `hypertable_detailed_size` total, tables + indexes + toast; every chunk compressed for this measurement)

| Hypertable | Size before | Size after | Ratio (total size) | Ratio (`hypertable_compression_stats`) |
|---|---|---|---|---|
{chr(10).join(rows)}

"Before" is the size when the benchmark started: chunks older than 1 day were already compressed by the policy, the newest were not. After, every chunk is compressed. The stats ratio covers compressed chunks only.

### Query latency: vehicle position reports per line per 5 minutes, last {WINDOW} (source: `EXPLAIN (ANALYZE)` server-side planning + execution, median of 5 after 1 warm-up)

| State | Continuous aggregate `vehicles_route_5m` (ms) | Raw `vehicles` (ms) | Speedup |
|---|---|---|---|
| Before forced compression | {tb['cagg_ms']} | {tb['raw_ms']} | {tb['speedup']}x |
| After compression | {ta['cagg_ms']} | {ta['raw_ms']} | {ta['speedup']}x |

Aggregate query:

```sql
{CAGG_SQL.strip()}
```

Raw query:

```sql
{RAW_SQL.strip()}
```

The dataset is only a few days of polling, so it is small for TimescaleDB; results at this size may not reflect larger volumes."""
    docs_util.upsert_section(DOCS, "real", "Real MBTA data", body)


if __name__ == "__main__":
    print(json.dumps(run(), indent=1, default=str))
    sys.exit(0)
