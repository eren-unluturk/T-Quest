from openapi_shape import check_shape, response_schema


def test_stop_facts(client, auth_headers):
    r = client.get("/stops/place-pktrm/facts", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["stop_id"] == "place-pktrm"
    assert body["stop_name"] == "Park Street"
    assert len(body["facts"]) >= 2
    check_shape(response_schema("/stops/{stop_id}/facts", "get"), body)


def test_stop_facts_404(client, auth_headers):
    r = client.get("/stops/place-nope/facts", headers=auth_headers)
    assert r.status_code == 404
    assert r.json() == {"detail": "unknown stop"}


def test_stop_facts_requires_auth(client):
    assert client.get("/stops/place-pktrm/facts").status_code == 401


def test_freedom_trail_sorted(client, auth_headers):
    r = client.get("/freedom-trail", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert [t["order"] for t in body] == list(range(1, 17))
    check_shape(response_schema("/freedom-trail", "get"), body)


def test_freedom_trail_requires_auth(client):
    assert client.get("/freedom-trail").status_code == 401


def test_fun_facts_without_auth(client):
    r = client.get("/fun-facts")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 10
    check_shape(response_schema("/fun-facts", "get"), body)


def test_fun_facts_limit_and_order(client):
    ordered = client.get("/fun-facts", params={"random": "false", "limit": 5}).json()
    assert [f["id"] for f in ordered] == ["fun.01", "fun.02", "fun.03", "fun.04", "fun.05"]
    again = client.get("/fun-facts", params={"random": "false", "limit": 5}).json()
    assert ordered == again
    assert len(client.get("/fun-facts", params={"limit": 50}).json()) == 25


def test_fun_facts_random_shuffles(client):
    runs = {
        tuple(f["id"] for f in client.get("/fun-facts", params={"limit": 25}).json())
        for _ in range(5)
    }
    assert len(runs) > 1


def test_fun_facts_limit_bounds(client):
    assert client.get("/fun-facts", params={"limit": 0}).status_code == 422
    assert client.get("/fun-facts", params={"limit": 51}).status_code == 422
