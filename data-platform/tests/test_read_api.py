from fastapi.testclient import TestClient

from data_platform.app import app

client = TestClient(app)


# ------------------------------------------------ no database needed
def test_predictions_requires_stop_or_route():
    assert client.get("/predictions").status_code == 422


def test_stops_requires_lat_and_lon_together():
    assert client.get("/stops", params={"lat": 42.3}).status_code == 422
    assert client.get("/stops", params={"lon": -71.0}).status_code == 422


def test_stops_limit_is_capped_at_500():
    assert client.get("/stops", params={"limit": 501}).status_code == 422


def test_routes_rejects_unknown_mode():
    assert client.get("/routes", params={"mode": "teleporter"}).status_code == 422


def test_cors_allows_any_origin():
    r = client.options("/routes", headers={"Origin": "http://example.com", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "*"


# ------------------------------------------------------ database
def test_stops_nearby_ordered_by_distance(api_world):
    lat, lon = api_world["origin"]
    r = client.get("/stops", params={"lat": lat, "lon": lon, "radius_m": 500})
    assert r.status_code == 200
    rows = r.json()
    ids = [s["id"] for s in rows]
    assert ids == api_world["stops"][:2]  # ~100 m and ~300 m, not the ~600 m one
    assert rows[0]["distance_m"] < rows[1]["distance_m"] < 500
    wide = client.get("/stops", params={"lat": lat, "lon": lon, "radius_m": 1000}).json()
    assert [s["id"] for s in wide] == api_world["stops"]


def test_stops_by_route(api_world):
    r = client.get("/stops", params={"route_id": api_world["route_a"]})
    assert sorted(s["id"] for s in r.json()) == sorted(api_world["stops"])


def test_stop_detail_and_404(api_world):
    r = client.get(f"/stops/{api_world['stops'][0]}")
    assert r.status_code == 200
    body = r.json()
    assert [x["id"] for x in body["routes"]] == [api_world["route_a"]]
    assert body["facts"][0]["body"] == "A fact"
    missing = client.get("/stops/does-not-exist")
    assert missing.status_code == 404
    assert "detail" in missing.json()


def test_routes_mode_filter_and_lines(api_world):
    r = client.get("/routes", params={"mode": "commuter_rail"})
    assert {api_world["route_a"], api_world["route_b"]} <= {x["id"] for x in r.json()}
    lines = {x["id"]: x for x in client.get("/lines").json()}
    line = lines[api_world["line_id"]]
    assert line["route_count"] == 2
    assert sorted(line["route_ids"]) == sorted([api_world["route_a"], api_world["route_b"]])


def test_vehicles_since_window(api_world):
    r = client.get("/vehicles", params={"stop_id": api_world["stops"][0], "since_s": 300})
    assert [v["vehicle_id"] for v in r.json()] == [api_world["vehicle_near"]]
    r = client.get("/vehicles", params={"stop_id": api_world["stops"][0], "since_s": 600})
    assert {v["vehicle_id"] for v in r.json()} == {api_world["vehicle_near"], api_world["vehicle_far"]}


def test_predictions_only_upcoming(api_world):
    r = client.get("/predictions", params={"stop_id": api_world["stops"][0]})
    assert [p["prediction_id"] for p in r.json()] == [f"p-{api_world['run']}-future"]


def test_alerts_active_default_and_all(api_world):
    r = client.get("/alerts", params={"route_id": api_world["route_a"]})
    assert [a["id"] for a in r.json()] == [api_world["alert_live"]]
    assert r.json()[0]["route_ids"] == [api_world["route_a"]]
    r = client.get("/alerts", params={"route_id": api_world["route_a"], "active": "false"})
    assert {a["id"] for a in r.json()} == {api_world["alert_live"], api_world["alert_old"]}
    r = client.get("/alerts", params={"stop_id": api_world["stops"][0]})
    assert [a["id"] for a in r.json()] == [api_world["alert_live"]]
