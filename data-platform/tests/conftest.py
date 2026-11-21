import uuid
from datetime import datetime, timedelta, timezone

import pytest

from data_platform import db, migrate


@pytest.fixture
def db_conn():
    """Connection to DATABASE_URL; skips the test when the DB is unreachable."""
    try:
        conn = db.connect(connect_timeout=3)
    except Exception as exc:
        pytest.skip(f"database unreachable: {exc}")
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def api_world(db_conn):
    """Throwaway transit and realtime rows with unique ids, visible to the API (autocommit).

    Stops sit near (10.0, 10.0), far from real Boston data, at roughly 100 m, 300 m and 600 m
    north of the origin point.
    """
    migrate.migrate()
    db_conn.autocommit = True
    run = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc)
    w = {
        "run": run,
        "origin": (10.0, 10.0),
        "line_id": f"line-T{run}",
        "route_a": f"T{run}-A",
        "route_b": f"T{run}-B",
        "stops": [f"T{run}-s{i}" for i in range(3)],
        "vehicle_near": f"v-{run}-near",
        "vehicle_far": f"v-{run}-far",
        "alert_live": f"alert-{run}-live",
        "alert_old": f"alert-{run}-old",
    }
    ex = db_conn.execute
    for rid, short in ((w["route_a"], "A"), (w["route_b"], "B")):
        ex("INSERT INTO routes (id, short_name, long_name, mode, route_type, color, line_id, sort_order)"
           " VALUES (%s, %s, %s, 'commuter_rail', 2, '112233', %s, 9999)",
           (rid, short, f"Test {short}", w["line_id"]))
    for stop_id, dlat in zip(w["stops"], (0.0009, 0.0027, 0.0054)):
        ex("INSERT INTO stops (id, name, lat, lon, is_freedom_trail) VALUES (%s, %s, %s, 10.0, false)",
           (stop_id, f"Test stop {stop_id}", 10.0 + dlat))
        ex("INSERT INTO route_stops (route_id, stop_id, direction_id, stop_sequence) VALUES (%s, %s, 0, 1)",
           (w["route_a"], stop_id))
    ex("INSERT INTO stop_facts (stop_id, kind, title, body) VALUES (%s, 'fast_fact', 'Fact', 'A fact')",
       (w["stops"][0],))

    for vid, secs in ((w["vehicle_near"], 200), (w["vehicle_far"], 400)):
        ex("INSERT INTO vehicles (time, vehicle_id, route_id, stop_id, lat, lon, current_status)"
           " VALUES (%s, %s, %s, %s, 10.0, 10.0, 'STOPPED_AT')",
           (now - timedelta(seconds=secs), vid, w["route_a"], w["stops"][0]))

    ex("INSERT INTO predictions (time, prediction_id, stop_id, route_id, arrival_time, departure_time)"
       " VALUES (%s, %s, %s, %s, %s, %s)",
       (now, f"p-{run}-future", w["stops"][0], w["route_a"], now + timedelta(minutes=5), now + timedelta(minutes=6)))
    ex("INSERT INTO predictions (time, prediction_id, stop_id, route_id, arrival_time, departure_time)"
       " VALUES (%s, %s, %s, %s, %s, %s)",
       (now, f"p-{run}-past", w["stops"][0], w["route_a"], now - timedelta(minutes=5), now - timedelta(minutes=4)))

    ex("INSERT INTO alerts (id, effect, severity, header, active_start, active_end) VALUES (%s, 'DELAY', 5, 'live',"
       " %s, %s)", (w["alert_live"], now - timedelta(hours=1), now + timedelta(hours=1)))
    ex("INSERT INTO alerts (id, effect, severity, header, active_start, active_end) VALUES (%s, 'DELAY', 3, 'old',"
       " %s, %s)", (w["alert_old"], now - timedelta(days=2), now - timedelta(days=1)))
    for aid in (w["alert_live"], w["alert_old"]):
        ex("INSERT INTO alert_entities (alert_id, route_id, stop_id) VALUES (%s, %s, %s)",
           (aid, w["route_a"], w["stops"][0]))

    yield w

    ex("DELETE FROM alerts WHERE id = ANY(%s)", ([w["alert_live"], w["alert_old"]],))
    ex("DELETE FROM predictions WHERE prediction_id LIKE %s", (f"p-{run}-%",))
    ex("DELETE FROM vehicles WHERE vehicle_id LIKE %s", (f"v-{run}-%",))
    ex("DELETE FROM stop_facts WHERE stop_id = ANY(%s)", (w["stops"],))
    ex("DELETE FROM route_stops WHERE route_id = ANY(%s)", ([w["route_a"], w["route_b"]],))
    ex("DELETE FROM stops WHERE id = ANY(%s)", (w["stops"],))
    ex("DELETE FROM routes WHERE id = ANY(%s)", ([w["route_a"], w["route_b"]],))
