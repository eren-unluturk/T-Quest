"""GET /me/travel on real MBTA route_stops with a throwaway synthetic rider (removed afterwards)."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from data_platform.app import app


@pytest.fixture
def rider(db_conn):
    db_conn.autocommit = True
    ex = db_conn.execute
    rows = ex("""SELECT route_id, stop_id, stop_sequence FROM route_stops
                  WHERE route_id = 'Red' AND direction_id = 0 AND stop_sequence IS NOT NULL
                  ORDER BY stop_sequence LIMIT 4""").fetchall()
    if len(rows) < 4:
        pytest.skip("real Red Line route_stops not loaded")
    name = f"travel_test_{uuid.uuid4().hex[:8]}"
    uid = ex("INSERT INTO users (username) VALUES (%s) RETURNING id", (name,)).fetchone()[0]
    now = datetime.now(timezone.utc)
    # rides stop 1 -> stop 3 of the route (two segments between them), 10 minutes apart
    for i, idx in enumerate((0, 2)):
        ex("""INSERT INTO rider_events (time, user_id, event_type, stop_id, route_id, is_synthetic)
              VALUES (%s, %s, 'checkin', %s, 'Red', true)""", (now - timedelta(minutes=10 - 10 * i), uid, rows[idx][1]))
    try:
        yield name, rows
    finally:
        ex("DELETE FROM rider_events WHERE user_id = %s", (uid,))
        ex("DELETE FROM users WHERE id = %s", (uid,))


def test_travel_miles_segments_and_lines(rider):
    name, _ = rider
    c = TestClient(app)
    r = c.get("/me/travel", headers={"Authorization": f"Bearer {name}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["traveled_segments"]) == 2
    assert body["total_miles"] > 0
    per = {l["line_id"]: l["miles"] for l in body["per_line"]}
    assert per["line-Red"] == body["total_miles"]
    assert len(per) >= 4 and sum(per.values()) == pytest.approx(body["total_miles"], abs=0.02)  # every subway line listed
    assert body["unlocked_spots"] == []


def test_travel_new_rider_has_zero_miles_and_all_lines(db_conn):
    db_conn.autocommit = True
    name = f"travel_test_{uuid.uuid4().hex[:8]}"
    db_conn.execute("INSERT INTO users (username) VALUES (%s)", (name,))
    try:
        body = TestClient(app).get("/me/travel", headers={"Authorization": f"Bearer {name}"}).json()
        assert body["total_miles"] == 0 and body["traveled_segments"] == []
        assert {"line-Red", "line-Blue", "line-Orange"} <= {l["line_id"] for l in body["per_line"]}
    finally:
        db_conn.execute("DELETE FROM users WHERE username = %s", (name,))


def test_travel_auth_and_unknown_user():
    c = TestClient(app)
    assert c.get("/me/travel").status_code == 401
    r = c.get("/me/travel", headers={"Authorization": "Bearer nobody_" + uuid.uuid4().hex})
    assert r.status_code == 200 and r.json()["total_miles"] == 0 and r.json()["traveled_segments"] == []
