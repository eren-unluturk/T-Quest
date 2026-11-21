import json
from datetime import datetime, timezone
from pathlib import Path

from data_platform import mbta

FIX = Path(__file__).parent / "fixtures" / "mbta"
POLL = datetime(2026, 11, 21, 18, 0, tzinfo=timezone.utc)


def load(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))["data"]


def test_parse_route():
    r = mbta.parse_route(load("routes")[0])
    assert r["id"] == "Red"
    assert r["mode"] == "subway" and r["route_type"] == 1
    assert r["short_name"] is None  # empty string becomes NULL
    assert r["long_name"] == "Red Line"
    assert r["line_id"] == "line-Red"
    assert r["color"] == "DA291C"


def test_route_type_modes():
    assert mbta.MODE_BY_ROUTE_TYPE == {
        0: "light_rail", 1: "subway", 2: "commuter_rail", 3: "bus", 4: "ferry"}


def test_parse_stop():
    s = mbta.parse_stop(load("stops")[0])
    assert s["id"] == "place-alfcl" and s["name"] == "Alewife"
    assert s["lat"] == 42.39583 and s["lon"] == -71.141287
    assert s["location_type"] == 1
    assert s["parent_station"] is None
    assert s["municipality"] == "Cambridge"


def test_parse_vehicle():
    res = load("vehicles")[0]
    v = mbta.parse_vehicle(res, POLL)
    assert v["time"] == POLL
    assert v["vehicle_id"] == res["id"]
    assert v["route_id"] == "Red"
    assert v["current_status"] == "IN_TRANSIT_TO"
    assert v["lat"] == 42.31624 and v["lon"] == -71.05217
    assert v["bearing"] == 350
    assert v["updated_at"].tzinfo is not None


def test_parse_prediction():
    res = load("predictions")[0]
    p = mbta.parse_prediction(res, POLL)
    assert p["prediction_id"] == res["id"]
    assert p["route_id"] == "Red" and p["stop_id"] == "70083"
    assert p["trip_id"] == "ADDED-1585095508"
    assert p["schedule_relationship"] == "SKIPPED"
    assert p["arrival_time"] is None


def test_parse_alert():
    res = load("alerts")[0]
    a = mbta.parse_alert(res)
    assert a["id"] == res["id"]
    assert a["effect"] == "STATION_CLOSURE" and a["severity"] == 7
    assert a["active_start"] < a["active_end"]
    assert {"route_id": "Green-C", "stop_id": "place-sumav", "route_type": 0, "direction_id": 1} in a["entities"]
    assert json.loads(a["raw"])["effect"] == "STATION_CLOSURE"


def test_parse_alert_open_ended_period_has_no_end():
    res = {"id": "x", "attributes": {"active_period": [
        {"start": "2026-11-01T00:00:00-05:00", "end": None}], "informed_entity": []}}
    a = mbta.parse_alert(res)
    assert a["active_end"] is None and a["active_start"] is not None
