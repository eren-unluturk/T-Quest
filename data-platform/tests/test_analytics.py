"""GET /analytics/system: pure helpers always; the live query only with a database."""
from fastapi.testclient import TestClient

from data_platform.app import app
from data_platform.routes.analytics import HourOfDay, extremes, line_extremes


def test_extremes_ignore_hours_without_service():
    prof = [HourOfDay(hour=3, avg_reports=0.0, days=2), HourOfDay(hour=8, avg_reports=900.5, days=2),
            HourOfDay(hour=14, avg_reports=400.0, days=2), HourOfDay(hour=23, avg_reports=60.0, days=2)]
    assert extremes(prof) == (8, 23)
    assert extremes([]) == (None, None)


def test_line_extremes():
    assert line_extremes({"line-Red": 500, "line-Blue": 100, "line-Orange": 0}) == ("line-Red", "line-Blue")
    assert line_extremes({"line-Red": 0}) == (None, None)


def test_system_snapshot_shape(db_conn):
    r = TestClient(app).get("/analytics/system?hours=3")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["lines"], "expected subway lines"
    assert {"line_id", "name", "vehicles_now", "reports_24h", "series"} <= set(b["lines"][0])
    assert isinstance(b["active_alerts"], int)
    assert all(0 <= p["hour"] <= 23 for p in b["hourly_profile"])
    assert TestClient(app).get("/analytics/system?hours=99").status_code == 422
