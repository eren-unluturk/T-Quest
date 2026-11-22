from fastapi.testclient import TestClient

from data_platform.app import app


def test_health_returns_ok_and_db_flag():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert isinstance(body["db"], bool)


def test_health_db_true(db_conn):
    r = TestClient(app).get("/health")
    assert r.json()["db"] is True


def test_health_reports_feed_freshness_field():
    body = TestClient(app).get("/health").json()
    assert "last_vehicle_at" in body
    assert body["last_vehicle_at"] is None or isinstance(body["last_vehicle_at"], str)
