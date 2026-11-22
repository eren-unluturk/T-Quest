"""Faved facts, stop-fact fallback and per-spot demo fun facts."""
from insights_sponsors.repo.ids import slug_to_uuid


def test_fave_list_and_unfave(client, auth_headers):
    assert client.get("/me/faves", headers=auth_headers).json() == []
    assert client.post("/me/faves/fact.pktrm.1", headers=auth_headers).status_code == 204
    assert client.post("/me/faves/fact.pktrm.1", headers=auth_headers).status_code == 204  # idempotent
    faves = client.get("/me/faves", headers=auth_headers).json()
    assert len(faves) == 1 and faves[0]["fact_id"] == "fact.pktrm.1"
    assert faves[0]["text"] and faves[0]["attribution"] and faves[0]["place"] == "Park Street"
    assert client.delete("/me/faves/fact.pktrm.1", headers=auth_headers).status_code == 204
    assert client.get("/me/faves", headers=auth_headers).json() == []


def test_faves_are_per_user_and_validate_ids(client, auth_headers):
    client.post("/me/faves/fact.pktrm.1", headers=auth_headers)
    assert client.get("/me/faves", headers={"Authorization": "Bearer someone-else"}).json() == []
    assert client.post("/me/faves/nope", headers=auth_headers).status_code == 404
    assert client.get("/me/faves").status_code == 401


def test_fave_a_loading_fact(client, auth_headers):
    fid = client.get("/loading-facts", params={"limit": 1}).json()[0]["id"]
    assert client.post(f"/me/faves/{fid}", headers=auth_headers).status_code == 204
    assert client.get("/me/faves", headers=auth_headers).json()[0]["kind"] == "loading_fact"


def test_stop_without_facts_gets_a_fallback(client, auth_headers):
    body = client.get("/stops/place-fenwy/facts", headers=auth_headers).json()
    own = client.get("/stops/place-pktrm/facts", headers=auth_headers).json()
    assert own["fallback"] is False and own["note"] is None
    if not body["facts"] or body["fallback"]:
        assert body["fallback"] is True and "No history recorded" in body["note"] and len(body["facts"]) == 1


def test_spot_fun_facts_are_demo_wording(client, auth_headers):
    r = client.get(f"/spots/{slug_to_uuid('spot.mintjulep')}", headers=auth_headers).json()
    assert "Demo placeholder" in r["fun_fact"] and "43 Brattle St" in r["fun_fact"]
    sample = client.get(f"/spots/{slug_to_uuid('spot.sample-noodle')}", headers=auth_headers).json()
    assert sample["fun_fact"].startswith("Fictional sample")
    for stop in ("place-harsq", "place-davis", "place-fenwy"):
        for s in client.get(f"/stops/{stop}/nearby", headers=auth_headers).json()["spots"]:
            assert s["fun_fact"], s["name"]
