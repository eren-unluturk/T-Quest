from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from openapi_shape import check_shape, response_schema

from insights_sponsors.analytics import compute_analytics, detect_home_line
from insights_sponsors.config import CURRENT_POLICY_VERSION
from insights_sponsors.models import RiderEvent
from insights_sponsors.recommend import recommend

SRC = Path(__file__).resolve().parent.parent / "src" / "insights_sponsors"


def ids(rec):
    return [i.id for i in rec.items]


def grant_place_visits(client, headers):
    r = client.post(
        "/consent",
        json={"scope": "place_visits", "policy_version": CURRENT_POLICY_VERSION},
        headers=headers,
    )
    assert r.status_code == 201


# ---- analytics (numbers hand-checked against tools generating data/seed/rider_events.json)
def test_analytics_all_time_user1(repo):
    a = compute_analytics(repo, "user-1", "all")
    assert a.stops_visited == 102
    assert a.unique_stops == 5
    assert a.lines_ridden == ["Green", "Red"]
    assert a.home_line == "Red"
    assert [(t.stop_id, t.visits) for t in a.top_stops] == [
        ("place-pktrm", 43),
        ("place-harsq", 25),
        ("place-dwnxg", 20),
        ("place-sstat", 10),
        ("place-gover", 4),
    ]
    assert a.neighborhoods_explored == ["Cambridge", "Downtown"]
    assert sum(w.checkins for w in a.by_week) == 102
    assert [w.week_start for w in a.by_week] == sorted(w.week_start for w in a.by_week)
    assert all(w.week_start.weekday() == 0 for w in a.by_week)


def test_analytics_month_and_week_windows(repo):
    month = compute_analytics(repo, "user-1", "month")
    assert month.stops_visited == 70
    assert month.unique_stops == 4
    assert month.lines_ridden == ["Red"]
    week = compute_analytics(repo, "user-1", "week")
    assert 0 < week.stops_visited < month.stops_visited
    assert sum(w.checkins for w in week.by_week) == week.stops_visited
    # home line does not depend on the period
    assert week.home_line == "Red"


def test_home_lines_of_demo_users(repo):
    assert compute_analytics(repo, "user-2", "all").home_line == "Orange"
    assert compute_analytics(repo, "user-3", "all").home_line == "Green"


def test_home_line_needs_five_recent_checkins():
    now = datetime.now(timezone.utc)

    def ev(days, n):
        return [
            RiderEvent(time=now - timedelta(days=days), user_id="u", event_type="checkin",
                       stop_id="place-pktrm", route_id="Red")
            for _ in range(n)
        ]

    assert detect_home_line(ev(3, 4), now) is None
    assert detect_home_line(ev(3, 5), now) == "Red"
    assert detect_home_line(ev(40, 9), now) is None  # outside 28 days
    assert detect_home_line([], now) is None


def test_analytics_unknown_user_is_empty(repo):
    a = compute_analytics(repo, "nobody", "all")
    assert a.stops_visited == 0 and a.unique_stops == 0
    assert a.home_line is None and a.by_week == [] and a.top_stops == []


def test_analytics_endpoint(client):
    h = {"Authorization": "Bearer user-1"}
    r = client.get("/analytics/me", params={"period": "all"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == "user-1" and body["stops_visited"] == 102
    check_shape(response_schema("/analytics/me", "get"), body)
    assert client.get("/analytics/me", headers=h).json()["period"] == "month"
    assert client.get("/analytics/me", params={"period": "year"}, headers=h).status_code == 422
    assert client.get("/analytics/me").status_code == 401


# ---- recommendations
def test_recommendations_exclude_visited_neighborhoods(repo):
    rec = recommend(repo, "user-1", limit=50)
    hoods = [i.id for i in rec.items if i.kind == "neighborhood"]
    assert "neighborhood.downtown" not in hoods and "neighborhood.cambridge" not in hoods
    # not reachable on Red or Green
    assert "neighborhood.charlestown" not in hoods
    assert hoods == [
        "neighborhood.back-bay",
        "neighborhood.fenway-kenmore",
        "neighborhood.west-end",
        "neighborhood.north-end",
    ]
    scores = [i.score for i in rec.items if i.kind == "neighborhood"]
    assert scores == [1.0, 0.5, 0.3333, 0.25]


def test_route_recommendation_connects_to_home_line(repo):
    rec = recommend(repo, "user-1", kind="route", limit=50)
    assert ids(rec) == ["Orange"]  # Blue shares no stop with Red; Green is already ridden
    assert rec.items[0].score == 0.8


def test_no_home_line_no_route_recs(repo):
    assert recommend(repo, "nobody", kind="route").items == []


def test_place_signal_requires_consent(client, repo):
    h = {"Authorization": "Bearer user-1"}
    spy = Mock(wraps=repo.place_visits)
    repo.place_visits = spy

    r = client.get("/recommendations", params={"kind": "stop"}, headers=h)
    assert r.status_code == 200 and r.json()["items"] == []
    spy.assert_not_called()

    grant_place_visits(client, h)
    r = client.get("/recommendations", params={"kind": "stop"}, headers=h)
    assert [i["id"] for i in r.json()["items"]] == ["place-haecl", "place-coecl"]
    assert [i["score"] for i in r.json()["items"]] == [0.4, 0.2]
    spy.assert_called_once()

    spy.reset_mock()
    client.delete("/consent/place_visits", headers=h)
    assert client.get("/recommendations", params={"kind": "stop"}, headers=h).json()["items"] == []
    spy.assert_not_called()


def test_only_recommend_reads_place_visits_and_after_has_consent():
    readers = {
        p.name
        for p in SRC.rglob("*.py")
        if "repo" not in p.parts and ".place_visits(" in p.read_text(encoding="utf-8")
    }
    assert readers == {"recommend.py"}
    text = (SRC / "recommend.py").read_text(encoding="utf-8")
    assert text.index("has_consent(repo, user_id") < text.index("repo.place_visits(")


def test_sponsored_flag_never_changes_order(repo):
    with_offers = recommend(repo, "user-1", limit=50)
    repo._offers = []
    without = recommend(repo, "user-1", limit=50)
    assert ids(with_offers) == ids(without)
    assert [i.score for i in with_offers.items] == [i.score for i in without.items]
    assert not any(i.sponsored or i.sponsor_id for i in without.items)


def test_sponsored_flag_from_active_quest_only(repo):
    by_id = {i.id: i for i in recommend(repo, "user-1", limit=50).items}
    assert by_id["neighborhood.fenway-kenmore"].sponsored is True
    assert by_id["neighborhood.fenway-kenmore"].sponsor_id == "sp.demo-sports"
    assert by_id["Orange"].sponsored is True  # passes Downtown Crossing (bakery quest)
    assert by_id["neighborhood.back-bay"].sponsored is False
    assert by_id["neighborhood.back-bay"].sponsor_id is None
    # an expired quest no longer sponsors
    now = datetime.now(timezone.utc)
    repo._offers = [
        o.model_copy(update={"ends_at": now - timedelta(days=1)})
        if o.placement == "sponsored_quest"
        else o
        for o in repo._offers
    ]
    assert not any(i.sponsored for i in recommend(repo, "user-1", limit=50).items)


def test_recommendations_endpoint(client):
    h = {"Authorization": "Bearer user-1"}
    r = client.get("/recommendations", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 5
    check_shape(response_schema("/recommendations", "get"), body)
    only = client.get("/recommendations", params={"kind": "neighborhood", "limit": 2}, headers=h)
    assert [i["kind"] for i in only.json()["items"]] == ["neighborhood"] * 2
    for bad in ({"limit": 0}, {"limit": 51}, {"kind": "bogus"}):
        assert client.get("/recommendations", params=bad, headers=h).status_code == 422
    assert client.get("/recommendations").status_code == 401


def test_recommendations_are_per_user(client):
    a = client.get("/recommendations", params={"limit": 50}, headers={"Authorization": "Bearer user-1"})
    b = client.get("/recommendations", params={"limit": 50}, headers={"Authorization": "Bearer user-2"})
    assert [i["id"] for i in a.json()["items"]] != [i["id"] for i in b.json()["items"]]


def test_seed_rider_events_shape(repo):
    users = {"user-1", "user-2", "user-3"}
    total = sum(len(repo.rider_events(u)) for u in users)
    assert 200 <= total <= 220
    assert not repo.rider_events("nobody")
    since = datetime.now(timezone.utc) - timedelta(days=30)
    assert all(e.time >= since for e in repo.rider_events("user-1", since))


@pytest.mark.parametrize("scope", ["location"])
def test_location_consent_does_not_unlock_place_visits(client, repo, scope):
    h = {"Authorization": "Bearer user-1"}
    client.post("/consent", json={"scope": scope, "policy_version": CURRENT_POLICY_VERSION}, headers=h)
    r = client.get("/recommendations", params={"kind": "stop"}, headers=h)
    assert r.json()["items"] == []
