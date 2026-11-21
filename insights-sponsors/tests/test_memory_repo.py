import re
from pathlib import Path

import pytest
import yaml
from insights_sponsors import spots as spots_mod
from insights_sponsors.routes import catalog as catalog_mod

from insights_sponsors import models
from insights_sponsors.repo import get_repository
from insights_sponsors.repo.memory import MemoryRepository

SPEC = Path(__file__).resolve().parent.parent / "openapi" / "insights-sponsors.yaml"
BRANDS = re.compile(
    r"starbucks|dunkin|nike|adidas|celtics|bruins|patriots|"
    r"target|walmart|h&m|zara|uniqlo|mcdonald|subway|trader joe",
    re.I,
)


@pytest.fixture
def repo() -> MemoryRepository:
    return MemoryRepository()


def test_seed_loads_and_counts(repo):
    assert len(repo.stops()) >= 23
    assert len(repo.trail_sites()) == 16
    assert len(repo.fun_facts()) == 25
    assert len(repo.stores()) == 10
    assert len(repo.offers()) == 21
    assert len(repo.physical_rewards()) == 6


def test_facts_reference_seeded_stops(repo):
    stop_ids = {s.id for s in repo.stops()}
    for stop in repo.stops():
        sf = repo.stop_facts(stop.id)
        assert sf is not None and 1 <= len(sf.facts) <= 3
        assert sf.stop_id in stop_ids
        assert sf.stop_name == stop.name
    assert repo.stop_facts("place-nope") is None


def test_trail_sites_ordered_and_reference_stops(repo):
    stop_ids = {s.id for s in repo.stops()}
    sites = repo.trail_sites()
    assert [t.order for t in sites] == list(range(1, 17))
    assert all(t.nearest_stop_id in stop_ids for t in sites)


def test_stores_offers_rewards_integrity(repo):
    stop_ids = {s.id for s in repo.stops()}
    store_ids = {s.id for s in repo.stores()}
    sponsor_ids = {s.id for s in repo.sponsors()}
    assert all(s.nearest_stop_id in stop_ids for s in repo.stores())
    for o in repo.offers():
        assert o.store_id is None or o.store_id in store_ids
        assert o.sponsor_id in sponsor_ids
        assert 1 <= o.min_rank <= 5
    for r in repo.physical_rewards():
        assert all(x.store_id in store_ids for x in r.stores)


def test_offer_coverage(repo):
    offers = repo.offers()
    assert {o.kind for o in offers} == {"discount", "free_item", "points_item"}
    assert {o.placement for o in offers} == {"local_pick", "sponsored_quest"}
    assert {o.min_rank for o in offers} == {1, 2, 3, 4, 5}
    assert any(o.required_badge_id for o in offers)
    assert {s.category for s in repo.stores()} == {"food", "clothing", "sports"}


def test_no_real_brand_names(repo):
    names = [s.name for s in repo.sponsors()] + [s.name for s in repo.stores()]
    names += [o.title + " " + o.description for o in repo.offers()]
    # Boston Red Sox, Mint Julep and Diesel Cafe are team-named placeholders, labeled demo
    for n in names:
        assert not BRANDS.search(n), n
    assert all(s.name.startswith("Demo") for s in repo.stores())
    assert all(s.demo_placeholder for s in repo.sponsors())


def test_offer_filters(repo):
    assert all(o.store_id == "st.cafe-parkst" for o in repo.offers(store_id="st.cafe-parkst"))
    assert {o.store_id for o in repo.offers(stop_id="place-dwnxg")} == {
        "st.bakery-dtx",
        "st.threads-dtx",
    }
    assert repo.offers(category="clothing")
    assert all(
        o.store_id is None or {s.id: s.category for s in repo.stores()}[o.store_id] == "clothing"
        for o in repo.offers(category="clothing")
    )


def test_stores_near_stop_sorted(repo):
    pairs = repo.stores_near_stop("place-pktrm", 5)
    assert len(pairs) == 5
    dists = [d for _, d in pairs]
    assert dists == sorted(dists)
    assert pairs[0][0].id == "st.cafe-parkst"
    assert repo.stores_near_stop("place-pktrm", 2).__len__() == 2
    assert repo.stores_near_stop("place-nope", 5) == []


def test_consent_round_trip(repo):
    assert repo.get_consents("u1") == []
    c = repo.set_consent("u1", "place_visits", True, "v1")
    assert c.granted and c.granted_at and c.revoked_at is None
    assert [x.scope for x in repo.get_consents("u1")] == ["place_visits"]
    r = repo.set_consent("u1", "place_visits", False, "v1")
    assert not r.granted and r.revoked_at and r.granted_at == c.granted_at
    assert repo.get_consents("u2") == []


def test_user_profile_defaults_and_override(repo):
    assert repo.user_rank("u1") == 1
    assert repo.user_badges("u1") == set()
    repo.set_user_profile("u1", rank=4, badges={"rank-3"})
    assert repo.user_rank("u1") == 4
    assert repo.user_badges("u1") == {"rank-3"}
    assert repo.user_rank("u2") == 1


def test_get_repository_singleton():
    assert get_repository() is get_repository()


def test_models_match_openapi_fields():
    schemas = yaml.safe_load(SPEC.read_text(encoding="utf-8"))["components"]["schemas"]
    checked = 0
    for name, schema in schemas.items():
        if schema.get("type") != "object":
            continue
        model = next(getattr(m, name) for m in (models, spots_mod, catalog_mod) if hasattr(m, name))
        assert set(model.model_fields) == set(schema["properties"]), name
        required = {k for k, f in model.model_fields.items() if f.is_required()}
        assert required == set(schema.get("required", [])), name
        checked += 1
    assert checked == 29


def test_seed_covers_neighborhoods_and_bus(repo):
    stops = repo.stops()
    assert len({s.neighborhood for s in stops}) >= 8
    assert len([s for s in stops if s.mode == "bus"]) >= 3
    assert all(s.mode in ("subway", "bus") for s in stops)
    # numeric ids are MBTA bus stops, place-* ids are stations
    assert all(s.mode == "bus" for s in stops if s.id.isdigit())
    # local picks exist outside Downtown
    assert repo.offers(stop_id="place-davis") and repo.offers(stop_id="place-forhl")


def test_trail_nearest_stop_is_closest_subway_stop(repo):
    from insights_sponsors.repo.memory import haversine_m

    subway = [s for s in repo.stops() if s.mode == "subway"]
    for t in repo.trail_sites():
        closest = min(subway, key=lambda s: haversine_m(t.lat, t.lon, s.lat, s.lon))
        assert t.nearest_stop_id == closest.id, t.name


def test_source_urls_are_https(repo):
    for stop in repo.stops():
        for fact in repo.stop_facts(stop.id).facts:
            assert fact.source_url is None or fact.source_url.startswith("https://"), fact.id
