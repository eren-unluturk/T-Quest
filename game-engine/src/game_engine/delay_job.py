"""Pay delay compensation for active outage alerts.

Run on a schedule (for example every few minutes):
    DATABASE_URL=... python -m game_engine.delay_job            (from game-engine/src)
    python -m game_engine.delay_job --dry-run                   (count only, writes nothing)

For each active alert whose effect is an outage, every DEMO user (username starts
with "demo_") whose home line (view home_line) is on an affected route gets
DELAY_COMPENSATION_POINTS once per alert. Real users are never paid. Writing needs
GE_ALLOW_DB_WRITES=1; --dry-run only counts. Rows are removed by demo_reset. Paid rows: points_ledger reason 'delay_compensation', ref_type
'alert', ref_id = alert id. Safe to run again: paid alerts are skipped.
"""
import os
import sys
import threading

from . import delay
from .pg_store import DEMO_PREFIX


def run(conn, dry_run=False, allow_writes=None):
    """Return {'alerts': n, 'paid': n, 'points': n}. Caller commits when conn is not autocommit."""
    if allow_writes is None:
        allow_writes = os.environ.get("GE_ALLOW_DB_WRITES") == "1"
    if not dry_run and not allow_writes:
        raise PermissionError("set GE_ALLOW_DB_WRITES=1 to pay (or use --dry-run)")
    effects = sorted(delay.OUTAGE_EFFECTS)
    alerts = conn.execute(
        "select distinct a.id, a.effect from active_alerts a join alert_entities e on e.alert_id = a.id "
        "where upper(a.effect) = any(%s) and e.route_id is not null", (effects,)).fetchall()
    paid = points = 0
    for alert_id, effect in alerts:
        users = conn.execute(
            "select distinct h.user_id, h.route_id from home_line h join alert_entities e on e.route_id = h.route_id "
            "join users u on u.id = h.user_id where e.alert_id = %s and starts_with(u.username, %s)",
            (alert_id, DEMO_PREFIX)).fetchall()
        done = {str(r[0]) for r in conn.execute(
            "select user_id from points_ledger where reason = 'delay_compensation' and ref_type = 'alert' "
            "and ref_id = %s", (alert_id,)).fetchall()}
        for user_id, route_id in users:
            pts = delay.compensation_points(
                alert_id=alert_id, alert_line=route_id, alert_effect=effect, user_home_line=route_id,
                already_paid_alerts={alert_id} if str(user_id) in done else set())
            if not pts:
                continue
            if not dry_run:
                conn.execute(
                    "insert into points_ledger (user_id, delta, reason, ref_type, ref_id, route_id) "
                    "values (%s, %s, 'delay_compensation', 'alert', %s, %s)", (user_id, pts, alert_id, route_id))
            done.add(str(user_id))
            paid += 1
            points += pts
    return {"alerts": len(alerts), "paid": paid, "points": points}


def run_standalone():
    """One run on its own connection (used by the background loop)."""
    from .pg_store import connect
    conn = connect()
    try:
        return run(conn, allow_writes=True)
    finally:
        conn.close()


def start_background(interval_s, runner=run_standalone, log=print):
    """Run the job every interval_s seconds in a daemon thread. Returns an Event; set() it to stop.

    A failed run is logged and the loop keeps going. Started by the app when DATABASE_URL and
    GE_ALLOW_DB_WRITES=1 are set (interval env DELAY_JOB_INTERVAL_S, default 300, 0 = off).
    """
    stop = threading.Event()

    def loop():
        while not stop.wait(interval_s):
            try:
                result = runner()
                if result.get("paid"):
                    log(f"delay job: {result}")
            except Exception as exc:  # keep the loop alive
                log(f"delay job failed: {exc}")

    threading.Thread(target=loop, daemon=True, name="delay-job").start()
    return stop


def main(argv):
    from .pg_store import connect
    conn = connect()
    result = run(conn, dry_run="--dry-run" in argv)
    print(result)
    conn.close()


if __name__ == "__main__":
    main(sys.argv[1:])