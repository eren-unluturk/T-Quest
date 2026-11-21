"""One-command verification for when a database exists.

Usage: python -m data_platform.verify [--skip-mbta] [--skip-bench] [--bench-days 2]

Works against local docker or Tiger Cloud (whatever DATABASE_URL points at). Every step is timed
and recorded as pass, fail or skipped; a failed step does not stop the run. Writes
verify/VERIFY.md and verify/verify.json and exits non-zero if any step failed.
Hostnames, passwords and IP addresses are redacted from everything that is written.
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from . import bench, db, ingest, load_static, mbta, migrate, seed

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "verify"
PASS, FAIL, SKIPPED = "pass", "fail", "skipped"


# ------------------------------------------------------------------ helpers
def redact(text: str, urls: list[str | None] = ()) -> str:
    """Remove hostnames, passwords and IP addresses from text."""
    for url in urls:
        if not url:
            continue
        parsed = urlparse(url)
        for secret in (parsed.hostname, parsed.password):
            if secret and len(secret) >= 3:
                text = text.replace(secret, "<redacted>")
    text = re.sub(r'(server|host) at "[^"]*"( \([^)]*\))?', r'\1 at "<host>"', text)
    text = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "<ip>", text)
    return text


def environment_label(url: str | None) -> str:
    if not url:
        return "unknown"
    return "tiger_cloud" if "sslmode=require" in url else "local"


def run_step(name: str, fn, skip_reason: str | None = None, urls: list[str | None] = ()) -> dict:
    """Run one step. `fn` returns a dict of details (may be empty); an exception means fail."""
    if skip_reason:
        return {"name": name, "status": SKIPPED, "seconds": 0.0, "detail": skip_reason, "error": None, "data": {}}
    started = time.monotonic()
    try:
        data = fn() or {}
        status, error = PASS, None
    except Exception as exc:  # noqa: BLE001 - every failure is recorded, not raised
        data = {}
        status = FAIL
        tail = traceback.format_exception_only(type(exc), exc)[-1].strip()
        error = redact(tail, urls)
    return {
        "name": name, "status": status, "seconds": round(time.monotonic() - started, 2),
        "detail": redact(str(data.get("summary", "")), urls), "error": error,
        "data": json.loads(redact(json.dumps(data, default=str), urls)),
    }


# --------------------------------------------------------------------- steps
def step_connect() -> dict:
    with db.connect(connect_timeout=10) as conn:
        version = conn.execute("SHOW server_version").fetchone()[0]
        ts = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'").fetchone()
    return {"summary": f"PostgreSQL {version}, timescaledb {ts[0] if ts else 'not installed yet'}",
            "postgres": version, "timescaledb": ts[0] if ts else None}


def step_migrate() -> dict:
    first = migrate.migrate()
    second = migrate.migrate()
    if second:
        raise AssertionError(f"second migrate run applied {second}; migrations are not idempotent")
    return {"summary": f"applied {len(first)} on first run, 0 on second", "applied": first}


def step_seed() -> dict:
    seed.seed()
    return {"summary": "dev seed applied"}


def step_mbta() -> dict:
    asyncio.run(load_static.run())

    async def one_cycle():
        async with mbta.MbtaClient() as client:
            with db.connect() as conn:
                return await ingest.run_cycle(client, conn)

    cycle = asyncio.run(one_cycle())
    with db.connect() as conn:
        counts = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                  for t in ("routes", "stops", "route_stops", "vehicles", "predictions", "alerts")}
    return {"summary": ", ".join(f"{k}={v}" for k, v in counts.items()), "counts": counts, "cycle": cycle}


def step_pytest() -> dict:
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                          cwd=ROOT, capture_output=True, text=True, timeout=1800)
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    summary = lines[-1] if lines else "no output"
    failed = [ln for ln in lines if ln.startswith(("FAILED", "ERROR"))]
    if proc.returncode != 0:
        raise AssertionError(f"pytest exit {proc.returncode}: {summary}; " + "; ".join(failed[:20]))
    return {"summary": summary}


def step_bench(days: int) -> dict:
    saved = os.environ.pop("TIGER_DATABASE_URL", None)  # verify only touches DATABASE_URL
    try:
        out = OUT_DIR / "bench"
        try:
            rc = bench.main(["--synthetic-days", str(days), "--users", "100", "--vehicles", "50",
                             "--runs", "5", "--out-dir", str(out)])
            if rc != 0:
                raise AssertionError(f"bench exit code {rc}")
            results = json.loads((out / "results.json").read_text(encoding="utf-8"))["environments"]["local"]
        finally:
            bench.main(["--cleanup"])
    finally:
        if saved is not None:
            os.environ["TIGER_DATABASE_URL"] = saved
    return {"summary": f"latency_ms={results['latency_ms']}", "compression": results["compression"],
            "latency_ms": results["latency_ms"]}


def step_introspect() -> dict:
    from psycopg.rows import dict_row
    queries = {
        "hypertables": "SELECT hypertable_name, num_chunks, compression_enabled FROM timescaledb_information.hypertables ORDER BY 1",
        "compression_settings": ("SELECT hypertable_name, attname, segmentby_column_index, orderby_column_index "
                                 "FROM timescaledb_information.compression_settings ORDER BY 1, 2"),
        "jobs": "SELECT job_id, proc_name, hypertable_name, schedule_interval::text AS schedule FROM timescaledb_information.jobs ORDER BY job_id",
        "continuous_aggregates": "SELECT view_name, materialized_only FROM timescaledb_information.continuous_aggregates ORDER BY 1",
    }
    data = {}
    with db.connect(row_factory=dict_row) as conn:
        for key, sql in queries.items():
            data[key] = [{k: (str(v) if not isinstance(v, (int, bool, type(None))) else v) for k, v in row.items()}
                         for row in conn.execute(sql).fetchall()]
    return {"summary": ", ".join(f"{k}={len(v)}" for k, v in data.items()), **data}


def default_steps(args) -> list[tuple]:
    """(name, fn, skip_reason) in run order."""
    mbta_skip = ("--skip-mbta given" if args.skip_mbta
                 else None if os.environ.get("MBTA_API_KEY") else "MBTA_API_KEY not set")
    return [
        ("connect", step_connect, None),
        ("migrate (twice, idempotent)", step_migrate, None),
        ("seed", step_seed, None),
        ("MBTA load_static + one ingest cycle", step_mbta, mbta_skip),
        ("pytest", step_pytest, None),
        ("bench (small) + cleanup", lambda: step_bench(args.bench_days), "--skip-bench given" if args.skip_bench else None),
        ("timescaledb introspection", step_introspect, None),
    ]


# -------------------------------------------------------------------- report
def build_report(steps: list[dict], environment: str) -> dict:
    failed = [s["name"] for s in steps if s["status"] == FAIL]
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "environment": environment, "ok": not failed, "failed_steps": failed, "steps": steps}


def _table(rows: list[dict]) -> str:
    if not rows:
        return "_none_\n"
    cols = list(rows[0])
    out = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    for r in rows:
        out += "| " + " | ".join(str(r[c]) for c in cols) + " |\n"
    return out


def render_markdown(report: dict) -> str:
    out = (f"# Verification report\n\nGenerated {report['generated_at']}  \nEnvironment: {report['environment']}  \n"
           f"Result: **{'PASS' if report['ok'] else 'FAIL'}**"
           + (f" (failed: {', '.join(report['failed_steps'])})" if report["failed_steps"] else "") + "\n\n")
    out += "| Step | Status | Seconds | Detail |\n|---|---|---|---|\n"
    for s in report["steps"]:
        detail = (s["error"] or s["detail"] or "").replace("|", "\\|").replace("\n", " ")
        out += f"| {s['name']} | {s['status']} | {s['seconds']} | {detail} |\n"
    for s in report["steps"]:
        if s["name"] == "timescaledb introspection" and s["status"] == PASS:
            for key in ("hypertables", "compression_settings", "jobs", "continuous_aggregates"):
                out += f"\n## {key.replace('_', ' ').capitalize()}\n\n{_table(s['data'].get(key, []))}"
    return out


def run(steps: list[tuple], out_dir: Path, environment: str, urls: list[str | None] = ()) -> int:
    results = [run_step(name, fn, skip, urls) for name, fn, skip in steps]
    report = build_report(results, environment)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "verify.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "VERIFY.md").write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    return 0 if report["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Verify the data-platform against a real database")
    p.add_argument("--skip-mbta", action="store_true")
    p.add_argument("--skip-bench", action="store_true")
    p.add_argument("--bench-days", type=int, default=2)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = p.parse_args(argv)
    url = os.environ.get("DATABASE_URL")
    return run(default_steps(args), args.out_dir, environment_label(url),
               urls=[url, os.environ.get("TIGER_DATABASE_URL")])


if __name__ == "__main__":
    sys.exit(main())
