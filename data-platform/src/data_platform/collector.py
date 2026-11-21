"""Standalone MBTA V3 live collector (plain program, no LLM, no agent loop).

    python -m data_platform.collector [--interval 15] [--prediction-every 2] [--alert-every 8]
                                      [--duration SECONDS]

Polls /vehicles every cycle, /predictions every N cycles and /alerts every M cycles, and writes
them in batches to the `vehicles`, `predictions`, `alerts` tables. Reads MBTA_API_KEY and
DATABASE_URL from the environment or ../.env. Resumable: it keeps no local state; inserts are
idempotent (ON CONFLICT), so a restart simply continues. Logs one status line per minute with row
counts only. Reconnects to the database and backs off (exponential, honouring Retry-After on 429).
Stops cleanly on Ctrl+C / SIGTERM. Secrets are redacted from every log line.
"""
import argparse
import asyncio
import logging
import os
import re
import signal
import sys
import time
from datetime import datetime, timezone

import psycopg

from . import db, ingest, mbta

log = logging.getLogger("collector")

MAX_BACKOFF_S = 120.0


def redact(text: str) -> str:
    """Strip secrets and connection strings from a message."""
    for name in ("MBTA_API_KEY", "DATABASE_URL"):
        v = os.environ.get(name)
        if v:
            text = text.replace(v, f"<{name}>")
    text = re.sub(r"postgres(ql)?://\S+", "<postgres-url>", text)
    text = re.sub(r"(?i)(api[_-]?key|password)=\S+", r"\1=<redacted>", text)
    return text


class Stats:
    def __init__(self) -> None:
        self.vehicles = self.predictions = self.alerts = self.errors = 0

    def reset(self) -> None:
        self.__init__()


def write_batch(conn, vehicles: list[dict], predictions: list[dict], alerts: list[dict]) -> None:
    ingest.write_cycle(conn, {"vehicles": vehicles, "predictions": predictions, "alerts": alerts})


async def collect(interval: float, pred_every: int, alert_every: int, duration: float | None) -> Stats:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows: fall back to KeyboardInterrupt handling in main()
            pass

    totals, window = Stats(), Stats()
    conn: psycopg.Connection | None = None
    route_ids: list[str] = []
    backoff = 1.0
    cycle = 0
    start = last_status = time.monotonic()

    async with mbta.MbtaClient() as client:
        while not stop.is_set():
            began = time.monotonic()
            if duration is not None and began - start >= duration:
                break
            try:
                if conn is None or conn.closed:
                    conn = db.connect(autocommit=False)
                    route_ids = ingest.subway_route_ids(conn)
                    conn.commit()
                poll_time = datetime.now(timezone.utc)
                vehicles = [mbta.parse_vehicle(v, poll_time) for v in
                            await client.get_all("/vehicles", {"filter[route_type]": "0,1,3"})]
                predictions, alerts = [], []
                if cycle % pred_every == 0 and route_ids:
                    predictions = [mbta.parse_prediction(p, poll_time) for p in
                                   await client.get_all("/predictions", {"filter[route]": ",".join(route_ids)})]
                if cycle % alert_every == 0:
                    alerts = [mbta.parse_alert(a) for a in
                              await client.get_all("/alerts", {"filter[datetime]": "NOW"})]
                write_batch(conn, vehicles, predictions, alerts)
                for s in (totals, window):
                    s.vehicles += len(vehicles)
                    s.predictions += len(predictions)
                    s.alerts += len(alerts)
                backoff = 1.0
                cycle += 1
            except Exception as exc:  # network, rate limit, database: back off and retry
                for s in (totals, window):
                    s.errors += 1
                log.warning("cycle failed (%s: %s); retry in %.0fs", type(exc).__name__,
                            redact(str(exc))[:120], backoff)
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn = None
                try:
                    await asyncio.wait_for(stop.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, MAX_BACKOFF_S)
                continue
            if time.monotonic() - last_status >= 60:
                log.info("rows/min vehicles=%d predictions=%d alerts=%d errors=%d",
                         window.vehicles, window.predictions, window.alerts, window.errors)
                window.reset()
                last_status = time.monotonic()
            try:
                await asyncio.wait_for(stop.wait(), timeout=max(0.0, interval - (time.monotonic() - began)))
            except asyncio.TimeoutError:
                pass
    if conn is not None and not conn.closed:
        conn.close()
    log.info("stopped: total vehicles=%d predictions=%d alerts=%d errors=%d",
             totals.vehicles, totals.predictions, totals.alerts, totals.errors)
    return totals


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MBTA live collector")
    ap.add_argument("--interval", type=float, default=15.0, help="seconds between polls")
    ap.add_argument("--prediction-every", type=int, default=2, help="poll predictions every N cycles")
    ap.add_argument("--alert-every", type=int, default=8, help="poll alerts every N cycles")
    ap.add_argument("--duration", type=float, default=None, help="stop after this many seconds")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        print("refusing to run: Anthropic credentials are set in the environment", file=sys.stderr)
        return 2
    try:
        asyncio.run(collect(args.interval, args.prediction_every, args.alert_every, args.duration))
    except KeyboardInterrupt:
        log.info("stopped (Ctrl+C)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
