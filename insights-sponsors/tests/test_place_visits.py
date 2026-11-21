from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from openapi_shape import check_shape, response_schema

from insights_sponsors.config import CURRENT_POLICY_VERSION
from insights_sponsors.models import PlaceVisit

SRC = Path(__file__).resolve().parent.parent / "src" / "insights_sponsors"
U9 = {"Authorization": "Bearer user-9"}  # no seeded data
U1 = {"Authorization": "Bearer user-1"}  # seeded place visits


def grant(client, headers, scope="place_visits"):
    r = client.post("/consent", json={"scope": scope, "policy_version": CURRENT_POLICY_VERSION}, headers=headers)
    assert r.status_code == 201


def body(**over):
    out = {
        "lat": 42.356449,
        "lon": -71.062449,
        "visited_at": datetime.now(timezone.utc).isoformat(),
        "place_category": "food",
    }
    out.update(over)
    return out


def post(client, headers=U9, **over):
    return client.post("/place-visits", json=body(**over), headers=headers)


# ---- consent gate
def test_403_without_consent_and_nothing_stored(client, repo):
    spy = Mock(wraps=repo.add_place_visit)
    repo.add_place_visit = spy
    r = post(client)
    assert r.status_code == 403
    assert r.json() == {"detail": "consent required: place_visits"}
    spy.assert_not_called()
    assert repo.place_visits("user-9") == []


def test_location_consent_alone_is_not_enough(client, repo):
    grant(client, U9, "location")
    assert post(client).status_code == 403
    assert repo.place_visits("user-9") == []


def test_revoked_consent_blocks_again(client, repo):
    grant(client, U9)
    assert post(client).status_code == 201
    client.delete("/consent/place_visits", headers=U9)
    assert post(client).status_code == 403


def test_requires_auth(client):
    assert client.post("/place-visits", json=body()).status_code == 401
    assert client.delete("/place-visits").status_code == 401


def test_only_the_gated_route_adds_visits():
    callers = {
        p.name
        for p in SRC.rglob("*.py")
        if "repo" not in p.parts and ".add_place_visit(" in p.read_text(encoding="utf-8")
    }
    assert callers == {"place_visits.py"}
    text = (SRC / "routes" / "place_visits.py").read_text(encoding="utf-8")
    assert text.index('require_consent("place_visits")') < text.index("repo.add_place_visit(")


# ---- accepted visits
def test_accepted_visit_is_rounded_and_acked(client, repo):
    grant(client, U9)
    r = post(client, store_id="st.cafe-parkst")
    assert r.status_code == 201
    assert r.json() == {"accepted": True, "retained_days": 90}
    check_shape(response_schema("/place-visits", "post", "201"), r.json())
    (v,) = repo.place_visits("user-9")
    assert (v.lat, v.lon) == (42.356, -71.062)  # about 100 m
    assert v.place_category == "food" and v.store_id == "st.cafe-parkst" and v.user_id == "user-9"


def test_time_window_edges(client, repo):
    grant(client, U9)
    now = datetime.now(timezone.utc)
    assert post(client, visited_at=(now - timedelta(days=6, hours=23)).isoformat()).status_code == 201
    assert post(client, visited_at=(now + timedelta(minutes=1)).isoformat()).status_code == 201
    naive = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    assert post(client, visited_at=naive).status_code == 201  # bare timestamps count as UTC
    assert len(repo.place_visits("user-9")) == 3


@pytest.mark.parametrize(
    "over",
    [
        {"visited_at": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()},
        {"visited_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()},
        {"lat": 90.5},
        {"lat": -91},
        {"lon": 180.1},
        {"lon": -181},
        {"place_category": "casino"},
        {"visited_at": "yesterday"},
    ],
)
def test_422_for_bad_visits(client, repo, over):
    grant(client, U9)
    assert post(client, **over).status_code == 422
    assert repo.place_visits("user-9") == []


def test_missing_fields_422(client):
    grant(client, U9)
    r = client.post("/place-visits", json={"lat": 42.0}, headers=U9)
    assert r.status_code == 422


# ---- deletion
def test_revoking_consent_deletes_visits(client, repo):
    grant(client, U9)
    post(client)
    post(client, place_category="sports")
    assert len(repo.place_visits("user-9")) == 2
    r = client.delete("/consent/place_visits", headers=U9)
    assert r.status_code == 200 and r.json()["granted"] is False
    assert repo.place_visits("user-9") == []
    assert not [v for v in repo._place_visits if v.user_id == "user-9"]
    # still nothing after granting again, and a repeat revoke is harmless
    grant(client, U9)
    assert repo.place_visits("user-9") == []
    assert client.delete("/consent/place_visits", headers=U9).status_code == 200


def test_revoking_other_scopes_keeps_visits(client, repo):
    grant(client, U9)
    grant(client, U9, "location")
    post(client)
    client.delete("/consent/location", headers=U9)
    assert len(repo.place_visits("user-9")) == 1


def test_revoking_only_deletes_that_users_visits(client, repo):
    grant(client, U9)
    post(client)
    seeded = len(repo.place_visits("user-1"))
    assert seeded > 0
    client.delete("/consent/place_visits", headers=U9)
    assert len(repo.place_visits("user-1")) == seeded


def test_revoke_removes_place_affinity_from_recommendations(client, repo):
    grant(client, U1)
    with_consent = client.get("/recommendations", params={"kind": "stop"}, headers=U1).json()["items"]
    assert [i["id"] for i in with_consent] == ["place-davis", "place-haecl", "place-coecl", "place-forhl"]
    client.delete("/consent/place_visits", headers=U1)
    assert repo.place_visits("user-1") == []
    assert client.get("/recommendations", params={"kind": "stop"}, headers=U1).json()["items"] == []
    grant(client, U1)  # the data is gone, so granting again does not bring the signal back
    assert client.get("/recommendations", params={"kind": "stop"}, headers=U1).json()["items"] == []


def test_delete_place_visits_works_without_consent(client, repo):
    assert repo.get_consents("user-1") == []  # never granted
    seeded = len(repo.place_visits("user-1"))
    assert seeded > 0
    r = client.delete("/place-visits", headers=U1)
    assert r.status_code == 200
    assert r.json() == {"deleted": seeded}
    check_shape(response_schema("/place-visits", "delete"), r.json())
    assert repo.place_visits("user-1") == []
    assert client.delete("/place-visits", headers=U1).json() == {"deleted": 0}


# ---- retention
def test_visits_older_than_90_days_are_never_returned(repo):
    now = datetime.now(timezone.utc)

    def visit(days):
        return PlaceVisit(time=now - timedelta(days=days), user_id="u", lat=1.0, lon=1.0, place_category="food")

    repo.add_place_visit("u", visit(100))
    repo.add_place_visit("u", visit(89))
    assert [round((now - v.time).days) for v in repo.place_visits("u")] == [89]
    assert [round((now - v.time).days) for v in repo.place_visits("u", now - timedelta(days=200))] == [89]
