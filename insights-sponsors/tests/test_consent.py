from fastapi import Depends
from openapi_shape import check_shape, response_schema

from insights_sponsors.config import CURRENT_POLICY_VERSION
from insights_sponsors.consent import has_consent, require_consent

V = CURRENT_POLICY_VERSION


def grant(client, headers, scope="place_visits", version=V):
    return client.post("/consent", json={"scope": scope, "policy_version": version}, headers=headers)


def by_scope(client, headers):
    return {c["scope"]: c for c in client.get("/consent", headers=headers).json()}


def test_default_state(client, auth_headers):
    r = client.get("/consent", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert [c["scope"] for c in body] == ["location", "place_visits"]
    for c in body:
        assert c["granted"] is False
        assert c["granted_at"] is None and c["revoked_at"] is None
    check_shape(response_schema("/consent", "get"), body)


def test_grant(client, auth_headers):
    r = grant(client, auth_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["granted"] is True and body["granted_at"] and body["revoked_at"] is None
    assert body["policy_version"] == V
    check_shape(response_schema("/consent", "post", "201"), body)
    state = by_scope(client, auth_headers)
    assert state["place_visits"]["granted"] is True
    assert state["location"]["granted"] is False


def test_revoke(client, auth_headers):
    grant(client, auth_headers)
    r = client.delete("/consent/place_visits", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["granted"] is False and body["revoked_at"] and body["granted_at"]
    check_shape(response_schema("/consent/{scope}", "delete"), body)


def test_revoke_is_idempotent(client, auth_headers):
    never = client.delete("/consent/location", headers=auth_headers)
    assert never.status_code == 200 and never.json()["granted"] is False
    grant(client, auth_headers)
    first = client.delete("/consent/place_visits", headers=auth_headers).json()
    second = client.delete("/consent/place_visits", headers=auth_headers)
    assert second.status_code == 200
    assert second.json() == first


def test_regrant_clears_revoked(client, auth_headers):
    first = grant(client, auth_headers).json()
    client.delete("/consent/place_visits", headers=auth_headers)
    again = grant(client, auth_headers).json()
    assert again["granted"] is True and again["revoked_at"] is None
    assert again["granted_at"] >= first["granted_at"]
    assert by_scope(client, auth_headers)["place_visits"]["revoked_at"] is None


def test_unknown_scope_422(client, auth_headers):
    assert grant(client, auth_headers, scope="contacts").status_code == 422
    assert client.delete("/consent/contacts", headers=auth_headers).status_code == 422


def test_policy_mismatch_409(client, auth_headers):
    r = grant(client, auth_headers, version="1999-01-01")
    assert r.status_code == 409
    assert r.json() == {"detail": "policy version mismatch", "current": V}
    assert by_scope(client, auth_headers)["place_visits"]["granted"] is False


def test_requires_auth(client):
    assert client.get("/consent").status_code == 401
    assert client.post("/consent", json={"scope": "location", "policy_version": V}).status_code == 401
    assert client.delete("/consent/location").status_code == 401


def test_isolated_per_user(client):
    a = {"Authorization": "Bearer user-a"}
    b = {"Authorization": "Bearer user-b"}
    grant(client, a)
    assert by_scope(client, a)["place_visits"]["granted"] is True
    assert by_scope(client, b)["place_visits"]["granted"] is False


def test_state_lives_in_repository(client, repo, auth_headers):
    grant(client, auth_headers)
    assert has_consent(repo, "user-1", "place_visits") is True
    assert has_consent(repo, "user-1", "location") is False
    client.delete("/consent/place_visits", headers=auth_headers)
    assert has_consent(repo, "user-1", "place_visits") is False


def test_require_consent_dependency(client, repo, auth_headers):
    @client.app.get("/_guarded")
    def guarded(uid: str = Depends(require_consent("place_visits"))):
        return {"user_id": uid}

    assert client.get("/_guarded").status_code == 401
    r = client.get("/_guarded", headers=auth_headers)
    assert r.status_code == 403
    assert r.json() == {"detail": "consent required: place_visits"}
    grant(client, auth_headers)
    ok = client.get("/_guarded", headers=auth_headers)
    assert ok.status_code == 200 and ok.json() == {"user_id": "user-1"}
    client.delete("/consent/place_visits", headers=auth_headers)
    assert client.get("/_guarded", headers=auth_headers).status_code == 403
