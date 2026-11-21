"""MBTA realtime ingestion worker.

Usage: python -m data_platform.ingest [--once] [--interval 15]
"""
import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime, timezone

from . import db, mbta

log = logging.getLogger("ingest")

INSERT_VEHICLE = """
INSERT INTO vehicles (time, vehicle_id, route_id, trip_id, stop_id, direction_id, current_status,
                      lat, lon, bearing, speed, label, updated_at)
VALUES (%(time)s, %(vehicle_id)s, %(route_id)s, %(trip_id)s, %(stop_id)s, %(direction_id)s,
        %(current_status)s, %(lat)s, %(lon)s, %(bearing)s, %(speed)s, %(label)s, %(updated_at)s)
ON CONFLICT DO NOTHING
"""

INSERT_PREDICTION = """
INSERT INTO predictions (time, prediction_id, stop_id, route_id, trip_id, direction_id,
                         arrival_time, departure_time, status, schedule_relationship)
VALUES (%(time)s, %(prediction_id)s, %(stop_id)s, %(route_id)s, %(trip_id)s, %(direction_id)s,
        %(arrival_time)s, %(departure_time)s, %(status)s, %(schedule_relationship)s)
ON CONFLICT DO NOTHING
"""

UPSERT_ALERT = """
INSERT INTO alerts (id, effect, cause, severity, header, description, lifecycle,
                    active_start, active_end, raw)
VALUES (%(id)s, %(effect)s, %(cause)s, %(severity)s, %(header)s, %(description)s, %(lifecycle)s,
        %(active_start)s, %(active_end)s, %(raw)s::jsonb)
ON CONFLICT (id) DO UPDATE SET
    effect = EXCLUDED.effect, cause = EXCLUDED.cause, severity = EXCLUDED.severity,
    header = EXCLUDED.header, description = EXCLUDED.description, lifecycle = EXCLUDED.lifecycle,
    active_start = EXCLUDED.active_start, active_end = EXCLUDED.active_end,
    raw = EXCLUDED.raw, last_seen_at = now()
"""

INSERT_ENTITY = """
INSERT INTO alert_entities (alert_id, route_id, stop_id, route_type, direction_id)
VALUES (%s, %s, %s, %s, %s)
"""


def subway_route_ids(conn) -> list[str]:
    rows = conn.execute("SELECT id FROM routes WHERE mode IN ('subway', 'light_rail')").fetchall()
    return [r[0] for r in rows]


async def fetch_cycle(client: mbta.MbtaClient, route_ids: list[str], poll_time: datetime) -> dict:
    """Fetch and parse one polling cycle. No database access."""
    vehicles_task = client.get_all("/vehicles", {"filter[route_type]": "0,1,3"})
    alerts_task = client.get_all("/alerts", {"filter[datetime]": "NOW"})
    if route_ids:
        predictions_task = client.get_all("/predictions", {"filter[route]": ",".join(route_ids)})
    else:
        predictions_task = asyncio.sleep(0, result=[])  # predictions require a route filter
    vehicles, predictions, alerts = await asyncio.gather(vehicles_task, predictions_task, alerts_task)
    return {
        "vehicles": [mbta.parse_vehicle(v, poll_time) for v in vehicles],
        "predictions": [mbta.parse_prediction(p, poll_time) for p in predictions],
        "alerts": [mbta.parse_alert(a) for a in alerts],
    }


def write_cycle(conn, data: dict) -> None:
    with conn.transaction():
        with conn.cursor() as cur:
            cur.executemany(INSERT_VEHICLE, data["vehicles"])
            cur.executemany(INSERT_PREDICTION, data["predictions"])
            for alert in data["alerts"]:
                cur.execute(UPSERT_ALERT, alert)
                cur.execute("DELETE FROM alert_entities WHERE alert_id = %s", (alert["id"],))
                cur.executemany(
                    INSERT_ENTITY,
                    [
                        (alert["id"], e["route_id"], e["stop_id"], e["route_type"], e["direction_id"])
                        for e in alert["entities"]
                    ],
                )


async def run_cycle(client: mbta.MbtaClient, conn) -> dict:
    started = time.monotonic()
    poll_time = datetime.now(timezone.utc)
    data = await fetch_cycle(client, subway_route_ids(conn), poll_time)
    write_cycle(conn, data)
    counts = {k: len(v) for k, v in data.items()}
    log.info("cycle ok %s in %.2fs", counts, time.monotonic() - started)
    return counts


async def run(once: bool, interval: float) -> None:
    async with mbta.MbtaClient() as client:
        while True:
            started = time.monotonic()
            try:
                with db.connect() as conn:
                    await run_cycle(client, conn)
            except Exception:
                log.exception("cycle failed; continuing")
            if once:
                return
            await asyncio.sleep(max(0.0, interval - (time.monotonic() - started)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MBTA realtime ingestion")
    parser.add_argument("--once", action="store_true", help="run one cycle and exit")
    parser.add_argument("--interval", type=float, default=15.0, help="seconds between cycles")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run(args.once, args.interval))
    return 0


if __name__ == "__main__":
    sys.exit(main())
