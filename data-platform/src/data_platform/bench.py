"""Demo benchmark: compression ratio and continuous-aggregate vs raw query latency.

Usage:
    python -m data_platform.bench [--synthetic-days 7] [--users 2000] [--vehicles 600]
    python -m data_platform.bench --cleanup

Synthetic rows are tagged so --cleanup removes them all: vehicle and prediction ids start
with `synthetic-`, users start with `bench_`, ledger rows have ref_type = 'synthetic'.
The database must already be migrated. If TIGER_DATABASE_URL is set, the same benchmark
also runs there (migrate it first: DATABASE_URL=<tiger url> python -m data_platform.migrate)
and results get a second column.
"""
import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg

from . import db, migrate

HYPERTABLES = ("vehicles", "predictions")
CAGGS = ("leaderboard_daily", "home_line_weekly", "user_route_daily", "personal_stats_daily")
OUT_DIR = Path(__file__).resolve().parents[2] / "bench"

ROUTES_SQL = "ARRAY['Red','Orange','Blue','Green-B','Green-C','Green-D','Green-E','1','66','39']"

# ---------------------------------------------------------------- compression
def compression_stats(tables: tuple[str, ...] = HYPERTABLES, url: str | None = None) -> dict[str, dict]:
    """Before/after bytes and ratio per hypertable (ratio is None until a chunk is compressed)."""
    out: dict[str, dict] = {}
    with db.connect(url) as conn:
        for table in tables:
            row = conn.execute(
                "SELECT coalesce(sum(before_compression_total_bytes), 0),"
                "       coalesce(sum(after_compression_total_bytes), 0)"
                " FROM hypertable_compression_stats(%s::regclass)",
                (table,),
            ).fetchone()
            before, after = int(row[0]), int(row[1])
            out[table] = {
                "before_bytes": before,
                "after_bytes": after,
                "ratio": round(before / after, 2) if after else None,
            }
    return out


# ------------------------------------------------------------------- cleanup
def cleanup(conn: psycopg.Connection) -> None:
    """Remove every synthetic row and user. conn must be in autocommit mode."""
    ex = conn.execute
    # Deleting from compressed chunks decompresses rows; lift the per-transaction cap for this session.
    ex("SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0")
    ex("DELETE FROM vehicles WHERE starts_with(vehicle_id, 'synthetic-')")
    ex("DELETE FROM predictions WHERE starts_with(prediction_id, 'synthetic-')")
    ex("DELETE FROM rider_events WHERE user_id IN (SELECT id FROM users WHERE starts_with(username, 'bench_'))")
    # points_ledger is append-only (trigger). Lift the guard only for this delete.
    ex("ALTER TABLE points_ledger DISABLE TRIGGER points_ledger_no_mutation")
    try:
        ex("DELETE FROM points_ledger WHERE ref_type = 'synthetic'")
    finally:
        ex("ALTER TABLE points_ledger ENABLE TRIGGER points_ledger_no_mutation")
    ex("DELETE FROM users WHERE starts_with(username, 'bench_')")
    for cagg in CAGGS:
        ex(f"CALL refresh_continuous_aggregate('{cagg}', NULL, NULL)")


# ------------------------------------------------------------------ generate
def generate(conn: psycopg.Connection, days: int, users: int, vehicles: int, poll_s: int) -> dict:
    """Create synthetic data ending now. conn must be in autocommit mode. Runs cleanup first."""
    cleanup(conn)
    ex = conn.execute
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now - timedelta(days=days)

    ex("INSERT INTO users (username, display_name) SELECT 'bench_' || lpad(g::text, 5, '0'), 'Bench ' || g"
       " FROM generate_series(1, %s) g ON CONFLICT DO NOTHING", (users,))

    preds = max(1, vehicles // 2)
    day = start
    while day < now:
        end = min(day + timedelta(days=1), now)
        ex(f"""
            INSERT INTO vehicles (time, vehicle_id, route_id, stop_id, direction_id, current_status,
                                  lat, lon, bearing, speed, label, updated_at)
            SELECT t, 'synthetic-' || v, ({ROUTES_SQL})[1 + mod(v, 10)],
                   'synthetic-stop-' || mod(v + extract(epoch FROM t)::bigint / 60, 40),
                   mod(v, 2)::smallint, 'IN_TRANSIT_TO',
                   42.30 + random() * 0.1, -71.15 + random() * 0.12,
                   (random() * 360)::real, (random() * 15)::real, v::text, t
            FROM generate_series(%(s)s::timestamptz, %(e)s::timestamptz - interval '1 millisecond',
                                 make_interval(secs => %(poll)s)) t
            CROSS JOIN generate_series(1, %(n)s) v""",
           {"s": day, "e": end, "poll": poll_s, "n": vehicles})
        ex(f"""
            INSERT INTO predictions (time, prediction_id, stop_id, route_id, trip_id, direction_id,
                                     arrival_time, departure_time, schedule_relationship)
            SELECT t, 'synthetic-' || p, 'synthetic-stop-' || mod(p, 40), ({ROUTES_SQL})[1 + mod(p, 10)],
                   'synthetic-trip-' || p, mod(p, 2)::smallint,
                   t + make_interval(secs => 60 + mod(p, 20) * 30),
                   t + make_interval(secs => 90 + mod(p, 20) * 30), 'SCHEDULED'
            FROM generate_series(%(s)s::timestamptz, %(e)s::timestamptz - interval '1 millisecond',
                                 interval '60 seconds') t
            CROSS JOIN generate_series(1, %(n)s) p""",
           {"s": day, "e": end, "n": preds})
        day = end

    # Per user and day: 4 check-ins and 3 ledger rows. Each user has a "home" route used 70% of the time.
    base = f"""
        FROM generate_series(date_trunc('day', %(s)s::timestamptz), %(now)s::timestamptz, interval '1 day') d
        CROSS JOIN (SELECT id, row_number() OVER (ORDER BY username) AS n
                    FROM users WHERE starts_with(username, 'bench_')) u
        CROSS JOIN generate_series(1, %(k)s) k
        CROSS JOIN LATERAL (
            SELECT CASE WHEN random() < 0.7 THEN ({ROUTES_SQL})[1 + mod(u.n, 10)::int]
                        ELSE ({ROUTES_SQL})[1 + floor(random() * 10)::int] END AS r,
                   LEAST(GREATEST(d + make_interval(secs => floor(random() * 86399)::int), %(s)s::timestamptz),
                         %(now)s::timestamptz) AS ts
        ) x"""
    ex(f"""
        INSERT INTO rider_events (time, user_id, event_type, route_id, mode, stop_id, lat, lon,
                                  points_awarded, payload)
        SELECT x.ts, u.id, 'checkin', x.r,
               CASE WHEN x.r ~ '^[0-9]' THEN 'bus' WHEN x.r LIKE 'Green%%' THEN 'light_rail' ELSE 'subway' END,
               'synthetic-stop-' || floor(random() * 40)::int,
               42.30 + random() * 0.1, -71.15 + random() * 0.12, 10, '{{"synthetic": true}}'
        {base}""", {"s": start, "now": now, "k": 4})
    ex(f"""
        INSERT INTO points_ledger (at, user_id, delta, reason, ref_type, route_id)
        SELECT x.ts, u.id, 2 + floor(random() * 19)::int, 'checkin', 'synthetic', x.r
        {base}""", {"s": start, "now": now, "k": 3})

    for table in (*HYPERTABLES, "rider_events", "points_ledger"):
        ex(f"ANALYZE {table}")
    return {"start": start.isoformat(), "end": now.isoformat()}


# ------------------------------------------------------------------- measure
def compress_old_chunks(conn: psycopg.Connection) -> None:
    for table in HYPERTABLES:
        conn.execute(
            "SELECT compress_chunk(c, if_not_compressed => true)"
            " FROM show_chunks(%s::regclass, older_than => interval '1 day') c", (table,))


def refresh_caggs(conn: psycopg.Connection) -> None:
    for cagg in CAGGS:
        conn.execute(f"CALL refresh_continuous_aggregate('{cagg}', NULL, NULL)")


def median_ms(fn, runs: int = 20) -> float:
    """Median wall-clock milliseconds of `fn()` over `runs` runs, after one warm-up call."""
    fn()
    samples = []
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return round(statistics.median(samples), 2)


LEADERBOARD_RAW = """
    WITH t AS (
        SELECT user_id, sum(delta) FILTER (WHERE delta > 0) AS pts FROM points_ledger
        WHERE at >= time_bucket('1 day', now() - interval '7 days') GROUP BY user_id)
    SELECT rank() OVER (ORDER BY t.pts DESC NULLS LAST), t.user_id, u.username, t.pts
    FROM t JOIN users u ON u.id = t.user_id ORDER BY 1, u.username LIMIT 50"""

HOME_LINE_RAW = """
    WITH recent AS (
        SELECT user_id, route_id, count(*) AS checkins_30d, max(time) AS last_ride FROM rider_events
        WHERE event_type IN ('checkin', 'ride_start') AND route_id IS NOT NULL
          AND time >= time_bucket('1 day', now() - interval '30 days') GROUP BY user_id, route_id),
    ranked AS (SELECT *, row_number() OVER (PARTITION BY user_id
                                            ORDER BY checkins_30d DESC, last_ride DESC, route_id) AS rn
               FROM recent)
    SELECT user_id, route_id, checkins_30d FROM ranked WHERE rn = 1 AND checkins_30d >= 5"""

VEHICLES_AT_STOP = """
    SELECT DISTINCT ON (vehicle_id) vehicle_id, time, route_id, stop_id, lat, lon FROM vehicles
    WHERE stop_id = 'synthetic-stop-1' AND time >= now() - interval '300 seconds'
    ORDER BY vehicle_id, time DESC"""


def measure(conn: psycopg.Connection, url: str | None, runs: int) -> dict:
    def q(sql):
        return lambda: conn.execute(sql).fetchall()

    latency = {
        "leaderboard_cagg": median_ms(q("SELECT * FROM leaderboard('global', 'week')"), runs),
        "leaderboard_raw": median_ms(q(LEADERBOARD_RAW), runs),
        "home_line_cagg": median_ms(q("SELECT * FROM home_line"), runs),
        "home_line_raw": median_ms(q(HOME_LINE_RAW), runs),
        "vehicles_at_stop_300s": median_ms(q(VEHICLES_AT_STOP), runs),
    }
    speedup = {
        "leaderboard": round(latency["leaderboard_raw"] / latency["leaderboard_cagg"], 2)
        if latency["leaderboard_cagg"] else None,
        "home_line": round(latency["home_line_raw"] / latency["home_line_cagg"], 2)
        if latency["home_line_cagg"] else None,
    }
    counts = {
        t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in ("vehicles", "predictions", "rider_events", "points_ledger")
    }
    sizes = {
        t: conn.execute("SELECT hypertable_size(%s::regclass)", (t,)).fetchone()[0]
        for t in ("rider_events", "points_ledger")
    }
    return {
        "row_counts": counts,
        "compression": compression_stats(url=url),
        "hypertable_bytes": sizes,
        "latency_ms": latency,
        "speedup_x": speedup,
    }


def run_environment(url: str | None, label: str, args) -> dict:
    migrate.migrate(url=url)  # make sure the schema exists (no-op when already migrated)
    with db.connect(url, autocommit=True) as conn:
        if args.cleanup:
            cleanup(conn)
            return {"cleaned": True}
        window = generate(conn, args.synthetic_days, args.users, args.vehicles, args.poll_seconds)
        compress_old_chunks(conn)
        refresh_caggs(conn)
        result = measure(conn, url, args.runs)
    result.update(environment=label, params={
        "synthetic_days": args.synthetic_days, "users": args.users,
        "vehicles": args.vehicles, "poll_seconds": args.poll_seconds, "runs": args.runs,
    }, data_window=window)
    return result


# -------------------------------------------------------------------- report
def _fmt_bytes(n) -> str:
    return "n/a" if n is None else f"{n / 1024 / 1024:.1f} MiB"


def render_markdown(results: dict) -> str:
    envs = results["environments"]
    names = list(envs)
    head = "| Metric | " + " | ".join(names) + " |\n|---|" + "---|" * len(names) + "\n"

    def row(label, fn):
        return f"| {label} | " + " | ".join(str(fn(envs[n])) for n in names) + " |\n"

    out = f"# Benchmark results\n\nGenerated {results['generated_at']}\n\n" + head
    out += row("Environment", lambda e: e["environment"])
    out += row("Synthetic days / users / vehicles",
               lambda e: f"{e['params']['synthetic_days']} / {e['params']['users']} / {e['params']['vehicles']}")
    for t in ("vehicles", "predictions", "rider_events", "points_ledger"):
        out += row(f"Rows: {t}", lambda e, t=t: f"{e['row_counts'][t]:,}")
    for t in HYPERTABLES:
        out += row(f"{t} size before compression",
                   lambda e, t=t: _fmt_bytes(e["compression"][t]["before_bytes"] or None))
        out += row(f"{t} size after compression",
                   lambda e, t=t: _fmt_bytes(e["compression"][t]["after_bytes"] or None))
        out += row(f"{t} compression ratio",
                   lambda e, t=t: (f"{e['compression'][t]['ratio']}x" if e["compression"][t]["ratio"] else "n/a"))
    labels = {
        "leaderboard_cagg": "Leaderboard (week), continuous aggregate (ms, median)",
        "leaderboard_raw": "Leaderboard (week), raw points_ledger (ms, median)",
        "home_line_cagg": "Home line, continuous aggregate (ms, median)",
        "home_line_raw": "Home line, raw rider_events (ms, median)",
        "vehicles_at_stop_300s": "Vehicles at a stop, last 300 s (ms, median)",
    }
    for key, label in labels.items():
        out += row(label, lambda e, key=key: e["latency_ms"][key])
    out += row("Leaderboard speedup", lambda e: f"{e['speedup_x']['leaderboard']}x")
    out += row("Home line speedup", lambda e: f"{e['speedup_x']['home_line']}x")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="T-Quest Tiger Data benchmark")
    p.add_argument("--synthetic-days", type=int, default=7)
    p.add_argument("--users", type=int, default=2000)
    p.add_argument("--vehicles", type=int, default=600)
    p.add_argument("--poll-seconds", type=int, default=15)
    p.add_argument("--runs", type=int, default=20)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--cleanup", action="store_true", help="remove all synthetic rows and users, then exit")
    args = p.parse_args(argv)

    targets = [("local", None)]
    if os.environ.get("TIGER_DATABASE_URL"):
        targets.append(("tiger_cloud", os.environ["TIGER_DATABASE_URL"]))

    envs = {}
    for name, url in targets:
        envs[name] = run_environment(url, name, args)
    if args.cleanup:
        print("synthetic data removed")
        return 0

    results = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "environments": envs}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (args.out_dir / "RESULTS.md").write_text(render_markdown(results), encoding="utf-8")
    print((args.out_dir / "RESULTS.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
