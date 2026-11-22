"""Seed a SEPARATE demo database for the public demo.

    python -m data_platform.seed_demo [--dry-run]

Reads DEMO_DATABASE_URL (target) and DATABASE_URL (source, read-only, for the MBTA snapshot).
Refuses to run when both point at the same database. Never prints a connection string.
Steps: apply migrations to the demo database; copy a snapshot of MBTA lines, routes, stops and route_stops
(static data only: no vehicles, predictions, alerts or rider data); load the demo catalog, nearby spots, labels,
rank data and tourist content with the insights-sponsors loaders. Safe to re-run (tables that already hold rows
are skipped for the snapshot, the loaders are idempotent).
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from dotenv import load_dotenv

from . import migrate

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT_TABLES = ["lines", "routes", "stops", "route_stops"]  # parents before children


def _identity(url: str) -> tuple:
    p = urlparse(url)
    return (p.hostname or "", p.port or 5432, (p.path or "").lstrip("/"))


def check_urls(demo: str | None, source: str | None) -> None:
    if not demo:
        raise SystemExit("DEMO_DATABASE_URL is not set")
    if not source:
        raise SystemExit("DATABASE_URL is not set (needed as the read-only source of the MBTA snapshot)")
    if demo == source or _identity(demo) == _identity(source):
        raise SystemExit("refusing to run: DEMO_DATABASE_URL points at the same database as DATABASE_URL")


def _columns(conn, table: str) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s "
        "ORDER BY ordinal_position", (table,)).fetchall()]


def copy_snapshot(src: psycopg.Connection, dst: psycopg.Connection, dry_run: bool) -> dict:
    counts = {}
    for t in SNAPSHOT_TABLES:
        cols = [c for c in _columns(src, t) if c in set(_columns(dst, t))] if not dry_run else _columns(src, t)
        n_src = src.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        if dry_run:
            counts[t] = f"would copy {n_src} rows"
            continue
        if dst.execute(f"SELECT count(*) FROM {t}").fetchone()[0] > 0:
            counts[t] = "skipped (already has rows)"
            continue
        collist = ", ".join(cols)
        with src.cursor().copy(f"COPY (SELECT {collist} FROM {t}) TO STDOUT") as out, \
                dst.cursor().copy(f"COPY {t} ({collist}) FROM STDIN") as inp:
            for chunk in out:
                inp.write(chunk)
        counts[t] = f"copied {n_src} rows"
    return counts


def run_loader(args: list[str], cwd: Path, demo_url: str) -> None:
    env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "DEMO_DATABASE_URL")}
    env["DATABASE_URL"] = demo_url
    env["PYTHONPATH"] = "src"
    r = subprocess.run([sys.executable, *args], cwd=cwd, env=env, capture_output=True, text=True)
    summary = (r.stdout.strip().splitlines() or [""])[-1][:300]
    if r.returncode != 0:
        raise SystemExit(f"loader {' '.join(args)} failed (exit {r.returncode}); details hidden to avoid leaking secrets")
    print(f"  {' '.join(args)}: {summary}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="check and print the plan; write nothing")
    args = ap.parse_args()
    load_dotenv(ROOT / ".env")
    demo, source = os.environ.get("DEMO_DATABASE_URL"), os.environ.get("DATABASE_URL")
    check_urls(demo, source)
    print("DEMO_DATABASE_URL: set, differs from DATABASE_URL" + (" (dry run)" if args.dry_run else ""))
    with psycopg.connect(source) as src:
        src.read_only = True
        if args.dry_run:
            print("Plan: apply migrations 0000-" + sorted(p.stem for p in migrate.MIGRATIONS_DIR.glob("[0-9]*.sql"))[-1][:4]
                  + " to the demo database")
            for t, c in copy_snapshot(src, src, True).items():
                print(f"  snapshot {t}: {c}")
            print("Plan: load demo catalog, spots, labels, rank data, tourist content (idempotent loaders)")
            return
        applied = migrate.migrate(url=demo)
        print(f"migrations applied: {len(applied)}")
        with psycopg.connect(demo) as dst:
            for t, c in copy_snapshot(src, dst, False).items():
                print(f"  snapshot {t}: {c}")
    run_loader(["scripts/load_seed.py"], ROOT / "insights-sponsors", demo)
    run_loader(["-m", "ingest_content.run"], ROOT / "insights-sponsors", demo)
    print("done")


if __name__ == "__main__":
    main()
