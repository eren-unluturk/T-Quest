"""Nearby spots: every filter combination, and the hard rule that pending labels are
never returned and never match a label filter."""

import json

import pytest
from openapi_shape import check_shape, response_schema

from insights_sponsors.repo.ids import slug_to_uuid
from insights_sponsors.repo.memory import DEFAULT_SEED_DIR
from insights_sponsors.spots import Spot, filter_spots, public_labels

HARVARD = "place-harsq"
DAVIS = "place-davis"
FENWAY = "place-fenwy"


def get(client, auth_headers, stop, **params):
    r = client.get(f"/stops/{stop}/nearby", params=params, headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()


def names(body):
    return [s["name"] for s in body["spots"]]


def test_no_filters_returns_all_active_and_matches_schema(client, auth_headers):
    body = get(client, auth_headers, HARVARD)
    check_shape(response_schema("/stops/{stop_id}/nearby", "get"), body)
    # 2 sponsored-or-sample at Harvard, the inactive spot is excluded
    assert set(names(body)) == {"Mint Julep", "Sample Noodle House (demo)", "Sample Books & Gifts (demo)"}
    assert body["total"] == 3


def test_unknown_stop_404_and_auth(client, auth_headers):
    assert client.get("/stops/place-nope/nearby", headers=auth_headers).status_code == 404
    assert client.get(f"/stops/{HARVARD}/nearby").status_code == 401


def test_every_item_has_placement_demo_category(client, auth_headers):
    for stop in (HARVARD, DAVIS, FENWAY):
        for s in get(client, auth_headers, stop)["spots"]:
            assert s["placement_type"] in ("sponsored", "listed")
            assert s["demo"] is True
            assert s["category"]["slug"]


def test_category_only(client, auth_headers):
    assert names(get(client, auth_headers, DAVIS, category="cafe")) == ["Diesel Cafe", "Sample Roasters (demo)"] or set(
        names(get(client, auth_headers, DAVIS, category="cafe"))
    ) == {"Diesel Cafe", "Sample Roasters (demo)"}


def test_category_repeatable_is_or(client, auth_headers):
    body = get(client, auth_headers, DAVIS, category=["cafe", "restaurant"])
    assert body["total"] == 3


def test_label_only(client, auth_headers):
    body = get(client, auth_headers, DAVIS, label="immigrant-owned")
    assert names(body) == ["Sample Roasters (demo)"]


def test_category_plus_label(client, auth_headers):
    body = get(client, auth_headers, DAVIS, category="cafe", label="immigrant-owned")
    assert names(body) == ["Sample Roasters (demo)"]
    assert get(client, auth_headers, DAVIS, category="restaurant", label="immigrant-owned")["total"] == 0


def test_match_all_vs_any(client, auth_headers):
    both = ["asian-owned", "woman-owned"]
    all_ = get(client, auth_headers, HARVARD, label=both)  # default match=all
    assert all_["total"] == 0
    any_ = get(client, auth_headers, HARVARD, label=both, match="any")
    assert set(names(any_)) == {"Sample Noodle House (demo)", "Sample Books & Gifts (demo)"}
    both_ok = get(client, auth_headers, HARVARD, label=["asian-owned", "family-owned"], match="all")
    assert names(both_ok) == ["Sample Noodle House (demo)"]


def test_every_label_filter_returns_something_in_the_demo(client, auth_headers):
    seen = set()
    for stop in (HARVARD, DAVIS, FENWAY):
        for chip in get(client, auth_headers, stop)["facets"]["labels"]:
            body = get(client, auth_headers, stop, label=chip["slug"])
            assert body["total"] == chip["count"] >= 1
            seen.add(chip["slug"])
    assert seen == {
        "local-independent", "woman-owned", "african-american-owned", "latino-owned",
        "asian-owned", "immigrant-owned", "veteran-owned", "lgbtq-owned", "family-owned",
    }


def test_sponsored_only_and_listed_only(client, auth_headers):
    sp = get(client, auth_headers, DAVIS, sponsored="true")
    assert names(sp) == ["Diesel Cafe"] and sp["spots"][0]["placement_type"] == "sponsored"
    listed = get(client, auth_headers, DAVIS, sponsored="false")
    assert all(s["placement_type"] == "listed" for s in listed["spots"]) and listed["total"] == 2


def test_name_search(client, auth_headers):
    assert names(get(client, auth_headers, DAVIS, q="taq")) == ["Sample Taqueria (demo)"]
    assert get(client, auth_headers, DAVIS, q="zzz")["total"] == 0


def test_include_demo_false_hides_demo(client, auth_headers):
    assert get(client, auth_headers, DAVIS, include_demo="false")["total"] == 0


def test_sort_and_paging(client, auth_headers):
    by_name = names(get(client, auth_headers, DAVIS, sort="name"))
    assert by_name == sorted(by_name, key=str.lower)
    first = names(get(client, auth_headers, DAVIS, sort="sponsored_first"))[0]
    assert first == "Diesel Cafe"
    dist = get(client, auth_headers, DAVIS, sort="distance")["spots"]
    known = [s["distance_m"] for s in dist if s["distance_m"] is not None]
    assert known == sorted(known) and dist[-1]["distance_m"] is None  # unknown distance last
    page = get(client, auth_headers, DAVIS, sort="name", limit=1, offset=1)
    assert page["total"] == 3 and len(page["spots"]) == 1 and page["spots"][0]["name"] == by_name[1]


def test_facets_count_whole_stop_not_the_filtered_set(client, auth_headers):
    plain = get(client, auth_headers, DAVIS)["facets"]
    filtered = get(client, auth_headers, DAVIS, category="cafe")["facets"]
    assert plain == filtered
    assert {c["slug"]: c["count"] for c in plain["categories"]} == {"cafe": 2, "restaurant": 1}


def test_sponsored_spots_carry_offers_and_demo_flag(client, auth_headers):
    fen = get(client, auth_headers, FENWAY, sponsored="true")
    assert names(fen) == ["Boston Red Sox"]
    offers = fen["spots"][0]["offers"]
    assert {"off.redsox-hat", "off.redsox-tickets-r2"} <= {o["id"] for o in offers}
    assert all(o["demo"] for o in offers)
    assert get(client, auth_headers, "place-kencl", sponsored="true")["total"] == 1


# ---- hard rule: pending labels are never exposed and never match -------------------------


def test_pending_labels_never_returned(client, auth_headers):
    pending = {
        (r["name"], l["label"])
        for r in json.loads((DEFAULT_SEED_DIR / "spots.json").read_text(encoding="utf-8"))["spots"]
        for l in r["labels"]
        if l["status"] == "pending"
    }
    assert pending, "seed must contain pending labels for this test to mean anything"
    for stop in (HARVARD, DAVIS, FENWAY):
        for s in get(client, auth_headers, stop)["spots"]:
            assert all(l["status"] in ("declared", "certified") for l in s["labels"])
            for name, slug in pending:
                if s["name"] == name:
                    assert slug not in {l["slug"] for l in s["labels"]}
            one = client.get(f"/spots/{s['id']}", headers=auth_headers).json()
            assert all(l["status"] in ("declared", "certified") for l in one["labels"])


def test_pending_labels_never_match_a_filter(client, auth_headers):
    # Mint Julep and Diesel Cafe only hold local-independent as pending.
    assert "Mint Julep" not in names(get(client, auth_headers, HARVARD, label="local-independent"))
    assert "Diesel Cafe" not in names(get(client, auth_headers, DAVIS, label="local-independent"))
    # Sample Taqueria holds woman-owned as pending only.
    assert get(client, auth_headers, DAVIS, label="woman-owned")["total"] == 0
    assert get(client, auth_headers, DAVIS, label="woman-owned", match="any")["total"] == 0
    # and the facets never count them
    labels = {c["slug"] for c in get(client, auth_headers, DAVIS)["facets"]["labels"]}
    assert "woman-owned" not in labels


def test_filter_logic_defends_even_if_a_repo_leaks_pending():
    from insights_sponsors.spots import CategoryRef, SpotLabel

    leaky = Spot(
        id="x", name="Leaky", category=CategoryRef(slug="cafe", display_name="Cafe"),
        placement_type="listed", demo=True, offers=[],
        labels=[SpotLabel(slug="woman-owned", display_name="Woman-owned", status="pending")],
    )
    assert filter_spots([leaky], labels=["woman-owned"]) == []
    assert filter_spots([leaky], labels=["woman-owned"], match="any") == []
    assert public_labels(leaky).labels == []


def test_declared_and_certified_labels_carry_evidence(client, auth_headers):
    for stop in (HARVARD, DAVIS, FENWAY):
        for s in get(client, auth_headers, stop)["spots"]:
            for l in s["labels"]:
                assert l["evidence_url"] or l["declaration_note"]
                assert l["verified_at"] and l["verified_by"]


def test_categories_labels_and_single_spot(client, auth_headers):
    cats = client.get("/categories", headers=auth_headers).json()
    assert {"restaurant", "cafe", "store", "clothing", "grocery", "bar", "other"} <= {c["slug"] for c in cats}
    labs = {l["slug"]: l["display_name"] for l in client.get("/labels", headers=auth_headers).json()}
    assert labs["african-american-owned"] == "African American-owned" and len(labs) == 9
    sid = str(slug_to_uuid("spot.sample-noodle"))
    one = client.get(f"/spots/{sid}", headers=auth_headers)
    assert one.status_code == 200 and one.json()["name"] == "Sample Noodle House (demo)"
    assert client.get("/spots/nope", headers=auth_headers).status_code == 404
    # inactive spots are not served
    assert client.get(f"/spots/{slug_to_uuid('spot.sample-closed')}", headers=auth_headers).status_code == 404


def test_three_demo_sponsors_are_labeled_placeholders(client, auth_headers):
    mint = get(client, auth_headers, HARVARD, sponsored="true")["spots"][0]
    assert mint["name"] == "Mint Julep" and mint["address"] == "43 Brattle St, Cambridge"
    assert mint["category"]["slug"] == "clothing" and mint["demo"] is True and mint["labels"] == []
    diesel = get(client, auth_headers, DAVIS, sponsored="true")["spots"][0]
    assert diesel["address"] == "257 Elm St, Somerville" and diesel["category"]["slug"] == "cafe"


def test_rank_tiers_and_offer_filters(client, auth_headers):
    tiers = client.get("/rank-tiers", headers=auth_headers).json()
    assert [t["discount_pct"] for t in tiers] == [3, 5, 7, 10, 12]
    assert [t["free_item"] for t in tiers] == [False, False, False, False, True]
    r1 = client.get("/offers", params={"rank": 1}, headers=auth_headers).json()
    assert r1 and all(o["min_rank"] <= 1 for o in r1)
    q = client.get("/offers", params={"placement": "sponsored_quest", "stop_id": DAVIS}, headers=auth_headers).json()
    assert [o["id"] for o in q] == ["off.diesel-quest"]
    fen = client.get("/offers", params={"stop_id": FENWAY}, headers=auth_headers).json()
    assert {"off.redsox-hat", "off.redsox-tickets-r2", "off.redsox-tickets-r5"} <= {o["id"] for o in fen}
