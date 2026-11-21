from datetime import datetime, timedelta, timezone

from openapi_shape import check_shape, response_schema

from insights_sponsors.eligibility import is_eligible


def ids(items):
    return {i["id"] for i in items}


def test_local_picks(client, auth_headers):
    r = client.get("/stops/place-pktrm/local-picks", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body
    assert body[0]["store"]["id"] == "st.cafe-parkst"
    assert all(o["placement"] == "local_pick" for p in body for o in p["offers"])
    assert [p["distance_m"] for p in body] == sorted(p["distance_m"] for p in body)
    check_shape(response_schema("/stops/{stop_id}/local-picks", "get"), body)


def test_local_picks_limit(client, auth_headers):
    r = client.get("/stops/place-pktrm/local-picks", params={"limit": 2}, headers=auth_headers)
    assert len(r.json()) == 2
    for bad in (0, 21):
        r = client.get("/stops/place-pktrm/local-picks", params={"limit": bad}, headers=auth_headers)
        assert r.status_code == 422


def test_local_picks_404_and_auth(client, auth_headers):
    assert client.get("/stops/place-nope/local-picks", headers=auth_headers).status_code == 404
    assert client.get("/stops/place-pktrm/local-picks").status_code == 401


def test_local_picks_exclude_quests_and_expired(client, repo, auth_headers):
    now = datetime.now(timezone.utc)
    # sponsored quests never show as local picks
    body = client.get("/stops/place-kencl/local-picks", headers=auth_headers).json()
    assert all(o["id"] != "off.sports-kenmore-quest" for p in body for o in p["offers"])
    # expire every local_pick offer of one store: the store drops out
    repo._offers = [
        o.model_copy(update={"ends_at": now - timedelta(days=1)})
        if o.store_id == "st.cafe-parkst"
        else o
        for o in repo._offers
    ]
    body = client.get("/stops/place-pktrm/local-picks", headers=auth_headers).json()
    assert "st.cafe-parkst" not in {p["store"]["id"] for p in body}
    # not yet started offers are inactive too
    repo._offers = [
        o.model_copy(update={"starts_at": now + timedelta(days=1)})
        if o.store_id == "st.bakery-dtx"
        else o
        for o in repo._offers
    ]
    body = client.get("/stops/place-dwnxg/local-picks", headers=auth_headers).json()
    assert "st.bakery-dtx" not in {p["store"]["id"] for p in body}


def test_offers_list_and_filters(client, auth_headers):
    r = client.get("/offers", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 14
    check_shape(response_schema("/offers", "get"), body)
    by_store = client.get("/offers", params={"store_id": "st.cafe-parkst"}, headers=auth_headers).json()
    assert ids(by_store) == {"off.cafe-parkst-r1", "off.cafe-parkst-quest"}
    by_stop = client.get("/offers", params={"stop_id": "place-dwnxg"}, headers=auth_headers).json()
    assert {o["store_id"] for o in by_stop} == {"st.bakery-dtx", "st.threads-dtx"}
    by_cat = client.get("/offers", params={"category": "sports"}, headers=auth_headers).json()
    assert {o["store_id"] for o in by_cat} == {"st.sports-north", "st.sports-kenmore"}
    assert client.get("/offers", params={"category": "bogus"}, headers=auth_headers).status_code == 422


def test_offers_requires_auth(client):
    assert client.get("/offers").status_code == 401


def test_offers_eligible_only_by_rank(client, repo, auth_headers):
    rank1 = client.get("/offers", params={"eligible_only": "true"}, headers=auth_headers).json()
    assert rank1 and all(o["min_rank"] == 1 for o in rank1)
    repo.set_user_profile("user-1", rank=5)
    rank5 = client.get("/offers", params={"eligible_only": "true"}, headers=auth_headers).json()
    # rank 5 qualifies for everything except the badge-gated quest
    assert ids(rank5) == ids(client.get("/offers", headers=auth_headers).json()) - {"off.sports-kenmore-quest"}


def test_offers_badge_gated(client, repo, auth_headers):
    repo.set_user_profile("user-1", rank=5)
    gated = "off.sports-kenmore-quest"
    r = client.get("/offers", params={"eligible_only": "true"}, headers=auth_headers).json()
    assert gated not in ids(r)
    repo.set_user_profile("user-1", rank=5, badges={"freedom-trail"})
    r = client.get("/offers", params={"eligible_only": "true"}, headers=auth_headers).json()
    assert gated in ids(r)
    # rank too low even with the badge
    repo.set_user_profile("user-1", rank=3, badges={"freedom-trail"})
    r = client.get("/offers", params={"eligible_only": "true"}, headers=auth_headers).json()
    assert gated not in ids(r)


def test_physical_rewards_catalog(client, auth_headers):
    r = client.get("/physical-rewards/catalog", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 6
    assert all(s["in_stock"] in (True, False) for item in body for s in item["stores"])
    check_shape(response_schema("/physical-rewards/catalog", "get"), body)
    assert client.get("/physical-rewards/catalog").status_code == 401


def test_is_eligible_pure(repo):
    plain = next(o for o in repo.offers() if o.id == "off.bakery-dtx-r2")
    gated = next(o for o in repo.offers() if o.id == "off.sports-kenmore-quest")
    assert not is_eligible(plain, 1, [])
    assert is_eligible(plain, 2, [])
    assert not is_eligible(gated, 5, [])
    assert is_eligible(gated, 4, ["freedom-trail"])
    assert not is_eligible(gated, 3, {"freedom-trail"})
