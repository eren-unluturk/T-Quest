"""Tourist content endpoints (memory mode serves Freedom Trail only). Attribution is mandatory."""
from openapi_shape import check_shape, response_schema


def test_stop_content_has_attribution_and_source(client, auth_headers):
    r = client.get("/stops/place-pktrm/content", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    check_shape(response_schema("/stops/{stop_id}/content", "get"), body)
    assert body, "Park Street should have Freedom Trail sites within 500 m"
    for i in body:
        assert i["attribution"] and i["source_url"] and i["license"]
        assert i["distance_m"] <= 500
    assert [i["distance_m"] for i in body] == sorted(i["distance_m"] for i in body)


def test_stop_content_unknown_stop_and_auth(client, auth_headers):
    assert client.get("/stops/place-nope/content", headers=auth_headers).status_code == 404
    assert client.get("/stops/place-pktrm/content").status_code == 401


def test_stop_content_category_filter(client, auth_headers):
    assert client.get("/stops/place-pktrm/content", params={"category": "none"}, headers=auth_headers).json() == []


def test_loading_facts_public_with_attribution(client):
    r = client.get("/loading-facts", params={"limit": 5})
    assert r.status_code == 200 and len(r.json()) == 5
    check_shape(response_schema("/loading-facts", "get"), r.json())
    assert all(f["attribution"] for f in r.json())


def test_freedom_trail_carries_attribution(client, auth_headers):
    for t in client.get("/freedom-trail", headers=auth_headers).json():
        assert t["attribution"] and t["source_url"]
