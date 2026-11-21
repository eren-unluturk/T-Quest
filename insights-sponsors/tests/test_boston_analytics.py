from datetime import datetime, timedelta, timezone

import pytest
from openapi_shape import check_shape, response_schema

from insights_sponsors.analytics import boston_analytics
from insights_sponsors.models import RiderEvent
from insights_sponsors.repo.memory import MemoryRepository

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
AUTH = {"Authorization": "Bearer user-1"}


def ev(user, stop, days_ago, n=1, route="Red"):
    return [
        RiderEvent(
            time=NOW - timedelta(days=days_ago, minutes=i),
            user_id=user,
            event_type="checkin",
            stop_id=stop,
            route_id=route,
        )
        for i in range(n)
    ]


def city(events) -> MemoryRepository:
    repo = MemoryRepository()
    repo._events = sorted(events, key=lambda e: e.time)
    return repo


# ---- endpoint, on the seed data
def test_endpoint_shape_and_default_period(client):
    r = client.get("/analytics/boston", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["period"] == "week"
    check_shape(response_schema("/analytics/boston", "get"), body)
    month = client.get("/analytics/boston", params={"period": "month"}, headers=AUTH)
    assert month.status_code == 200 and month.json()["period"] == "month"
    check_shape(response_schema("/analytics/boston", "get"), month.json())


def test_endpoint_requires_auth_and_valid_period(client):
    assert client.get("/analytics/boston").status_code == 401
    assert client.get("/analytics/boston", params={"period": "all"}, headers=AUTH).status_code == 422


@pytest.mark.parametrize("period", ["week", "month"])
def test_seed_city_view_is_anonymous(client, period):
    r = client.get("/analytics/boston", params={"period": period}, headers=AUTH)
    assert "user-" not in r.text and "user_id" not in r.text
    body = r.json()
    assert body["active_riders"] >= 3
    stops = {s["stop_id"] for s in body["busiest_stops"]}
    assert "place-pktrm" in stops
    # Aquarium is only visited by two riders in the seed, so it is never shown
    assert "place-aqucl" not in stops
    assert all(s["checkins"] > 0 for s in body["busiest_stops"])
    assert len(body["busiest_stops"]) <= 10 and len(body["trending_neighborhoods"]) <= 5


def test_seed_red_line_has_a_daily_series(client):
    body = client.get("/analytics/boston", headers=AUTH).json()
    red = next(line for line in body["lines"] if line["route_id"] == "Red")
    assert red["checkins"] >= 3
    # users 4-6 ride Red together on three recent days, so those days pass k=3
    assert len(red["by_day"]) >= 3
    assert all(d["checkins"] >= 3 for d in red["by_day"])
    assert [d["day"] for d in red["by_day"]] == sorted(d["day"] for d in red["by_day"])


# ---- rules, on hand-built data
def test_stop_with_two_riders_is_suppressed():
    events = ev("a", "place-pktrm", 1, 2) + ev("b", "place-pktrm", 1, 2) + ev("c", "place-pktrm", 2)
    events += ev("a", "place-aqucl", 1, 5, "Blue") + ev("b", "place-aqucl", 2, 5, "Blue")
    out = boston_analytics(city(events), "week", NOW)
    assert [(s.stop_id, s.checkins) for s in out.busiest_stops] == [("place-pktrm", 5)]
    assert out.active_riders == 3
    assert out.total_checkins == 15
    assert "Blue" not in {line.route_id for line in out.lines}


def test_fewer_than_three_active_riders_reports_zero():
    events = ev("a", "place-pktrm", 1, 4) + ev("b", "place-pktrm", 2, 4)
    out = boston_analytics(city(events), "week", NOW)
    assert out.active_riders == 0 and out.total_checkins == 0
    assert out.busiest_stops == [] and out.trending_neighborhoods == [] and out.lines == []


def test_change_pct_and_trending_rules():
    events = []
    # Downtown: 12 now (3 riders), 6 before (3 riders) -> +100.0
    for u in "abc":
        events += ev(u, "place-pktrm", 1, 4) + ev(u, "place-pktrm", 9, 2)
    # Cambridge: 6 now, 9 before (3 riders each) -> -33.3
    for u in "abc":
        events += ev(u, "place-harsq", 2, 2) + ev(u, "place-harsq", 10, 3)
    # Back Bay: 5 now (3 riders), nothing before -> +100.0 (no previous data)
    events += ev("a", "place-coecl", 3, 2) + ev("b", "place-coecl", 3, 2) + ev("c", "place-coecl", 3)
    # Allston: 6 now (3 riders), 12 before from only 2 riders -> previous suppressed -> +100.0
    for u in "abc":
        events += ev(u, "place-harvd", 4, 2, "Green")
    events += ev("a", "place-harvd", 11, 6, "Green") + ev("b", "place-harvd", 11, 6, "Green")
    # Fenway-Kenmore: only 4 check-ins now -> below the 5 minimum
    events += ev("a", "place-kencl", 1, 2, "Green") + ev("b", "place-kencl", 1, 1, "Green") + ev("c", "place-kencl", 1, 1, "Green")
    # West End: 6 check-ins from 2 riders -> below k
    events += ev("a", "place-north", 1, 3, "Green") + ev("b", "place-north", 1, 3, "Green")

    out = boston_analytics(city(events), "week", NOW)
    got = [(t.neighborhood, t.checkins, t.change_pct) for t in out.trending_neighborhoods]
    assert got == [
        ("Downtown", 12, 100.0),
        ("Allston", 6, 100.0),
        ("Back Bay", 5, 100.0),
        ("Cambridge", 6, -33.3),
    ]


def test_trending_is_capped_at_five():
    stops = ["place-pktrm", "place-harsq", "place-coecl", "place-harvd", "place-kencl", "place-forhl", "place-davis"]
    events = []
    for s in stops:
        for u in "abc":
            events += ev(u, s, 1, 2, "Green")
    out = boston_analytics(city(events), "week", NOW)
    assert len(out.trending_neighborhoods) == 5


def test_line_days_below_three_riders_are_omitted_but_still_counted():
    events = []
    for u in "abc":
        events += ev(u, "place-pktrm", 1, 2)  # day 1: three riders, 6 check-ins
    events += ev("a", "place-pktrm", 2, 3) + ev("b", "place-pktrm", 2, 3)  # day 2: two riders
    out = boston_analytics(city(events), "week", NOW)
    red = next(line for line in out.lines if line.route_id == "Red")
    assert red.checkins == 12
    assert [(d.day, d.checkins) for d in red.by_day] == [((NOW - timedelta(days=1)).date(), 6)]


def test_period_windows():
    events = []
    for u in "abc":
        events += ev(u, "place-pktrm", 20)  # outside a week, inside a month
    assert boston_analytics(city(events), "week", NOW).total_checkins == 0
    assert boston_analytics(city(events), "month", NOW).total_checkins == 3


def test_no_user_ids_in_model_dump():
    events = ev("alice", "place-pktrm", 1, 2) + ev("bob", "place-pktrm", 1, 2) + ev("carol", "place-pktrm", 1)
    out = boston_analytics(city(events), "week", NOW)
    dumped = out.model_dump_json()
    assert not any(name in dumped for name in ("alice", "bob", "carol", "user"))
