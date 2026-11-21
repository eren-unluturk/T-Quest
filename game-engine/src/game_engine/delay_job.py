"""Pay delay compensation for active outage alerts.

Run on a schedule (for example every few minutes):
    DATABASE_URL=... python -m game_engine.delay_job            (from game-engine/src)
    python -m game_engine.delay_job --dry-run                   (count only, writes nothing)

For each active alert whose effect is an outage, every user whose home line
(view home_line) is on an affected route gets DELAY_COMPENSATION_POINTS once
per alert. Paid rows: points_ledger reason 'delay_compensation', ref_type
'alert', ref_id = alert id. Safe to run again: paid alerts are skipped.
"""
import sys

from . import delay


def run(conn, dry_run=False):
    """Return {'alerts': n, 'paid': n, 'points': n}. Caller commits when conn is not autocommit."""
    effects = sorted(delay.OUTAGE_EFFECTS)
    alerts = conn.execute(
        "select distinct a.id, a.effect from active_alerts a join alert_entities e on e.alert_id = a.id "
        "where upper(a.effect) = any(%s) and e.route_id is not null", (effects,)).fetchall()
    paid = points = 0
    for alert_id, effect in alerts:
        users = conn.execute(
            "select distinct h.user_id, h.route_id from home_line h join alert_entities e on e.route_id = h.route_id "
            "where e.alert_id = %s", (alert_id,)).fetchall()
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


def main(argv):
    from .pg_store import connect
    conn = connect()
    result = run(conn, dry_run="--dry-run" in argv)
    print(result)
    conn.close()


if __name__ == "__main__":
    main(sys.argv[1:])