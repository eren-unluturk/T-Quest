"""Runs against the real Tiger Data database. Skipped when no database is reachable.
Run with the stale shell DATABASE_URL unset so .env is used:  pytest -m db
Seed rows are idempotent; the tests only read after loading the seed."""

import importlib.util
import sys
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")
from fastapi.testclient import TestClient

from insights_sponsors.config import settings
from insights_sponsors.main import create_app
from insights_sponsors.repo import get_repository
from insights_sponsors.repo.ids import slug_to_uuid

pytestmark = pytest.mark.db
AUTH = {"Authorization": "Bearer user-1"}


def _reachable() -> bool:
    if not settings.database_url:
        return False
    try:
        with psycopg.connect(settings.database_url, connect_timeout=5) as c:
            c.execute("SELECT 1 FROM nearby_spots LIMIT 1")
        return True
    except Exception:
        return False


if not _reachable():
    pytest.skip("no reachable database with migration 0010", allow_module_level=True)


def _loader():
    spec = importlib.util.spec_from_file_location(
        "load_seed", Path(__file__).resolve().parents[1] / "scripts" / "load_seed.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def client():
    from insights_sponsors.repo.postgres import PostgresRepository

    with psycopg.connect(settings.database_url) as conn:
        _loader().run(conn)
    repo = PostgresRepository()
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repo
    return TestClient(app)


def names(r):
    return {s["name"] for s in r.json()["spots"]}


def test_seed_is_idempotent():
    def counts():
        with psycopg.connect(settings.database_url) as c:
            return [c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                    for t in ("nearby_spots", "spot_labels", "spot_stop_links", "offers", "sponsors")]

    before = counts()
    with psycopg.connect(settings.database_url) as conn:
        _loader().run(conn)
    assert counts() == before


def test_nearby_filters_on_postgres(client):
    r = client.get("/stops/place-davis/nearby", headers=AUTH)
    assert r.status_code == 200
    assert names(r) == {"Diesel Cafe", "Sample Roasters (demo)", "Sample Taqueria (demo)"}
    assert names(client.get("/stops/place-davis/nearby", params={"category": "cafe", "label": "immigrant-owned"}, headers=AUTH)) == {"Sample Roasters (demo)"}
    both = client.get("/stops/place-harsq/nearby", params={"label": ["asian-owned", "woman-owned"], "match": "any"}, headers=AUTH)
    assert names(both) == {"Sample Noodle House (demo)", "Sample Books & Gifts (demo)"}
    assert names(client.get("/stops/place-fenwy/nearby", params={"sponsored": "true"}, headers=AUTH)) == {"Boston Red Sox"}
    assert names(client.get("/stops/place-kencl/nearby", params={"sponsored": "true"}, headers=AUTH)) == {"Boston Red Sox"}


def test_pending_labels_hidden_in_postgres(client):
    with psycopg.connect(settings.database_url) as c:
        pending = c.execute("SELECT count(*) FROM spot_labels WHERE status = 'pending'").fetchone()[0]
    assert pending >= 3  # Mint Julep, Diesel Cafe, Sample Taqueria woman-owned
    assert client.get("/stops/place-davis/nearby", params={"label": "woman-owned"}, headers=AUTH).json()["total"] == 0
    assert "Diesel Cafe" not in names(client.get("/stops/place-davis/nearby", params={"label": "local-independent"}, headers=AUTH))
    for stop in ("place-harsq", "place-davis", "place-fenwy"):
        for s in client.get(f"/stops/{stop}/nearby", headers=AUTH).json()["spots"]:
            assert all(l["status"] in ("declared", "certified") for l in s["labels"])


def test_db_rejects_declared_label_without_evidence():
    with psycopg.connect(settings.database_url) as c:
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute(
                "INSERT INTO spot_labels (spot_id, label_slug, status) VALUES (%s, 'family-owned', 'declared')",
                (slug_to_uuid("spot.sample-grocery"),),
            )


def test_offers_rewards_and_spot_detail_on_postgres(client):
    fen = client.get("/offers", params={"stop_id": "place-fenwy"}, headers=AUTH).json()
    assert {o["title"] for o in fen} >= {"Red Sox hat (demo)", "Ticket discount, rank 2 (demo)"}
    assert all(o["demo"] for o in fen)
    cat = client.get("/physical-rewards/catalog", headers=AUTH).json()
    assert len(cat) >= 6 and all(x["badge_id"] for x in cat)
    one = client.get(f"/spots/{slug_to_uuid('spot.mintjulep')}", headers=AUTH).json()
    assert one["address"] == "43 Brattle St, Cambridge" and one["labels"] == [] and one["demo"] is True
    assert client.get("/spots/not-a-uuid", headers=AUTH).status_code == 404
    assert client.get("/stops/place-nope/nearby", headers=AUTH).status_code == 404


def test_tourist_content_on_postgres(client):
    with psycopg.connect(settings.database_url) as c:
        n = c.execute("SELECT count(*) FROM content_items").fetchone()[0]
    if n == 0:
        pytest.skip("run python -m ingest_content.run first")
    r = client.get("/stops/place-pktrm/content", headers=AUTH)
    assert r.status_code == 200 and r.json()
    for i in r.json():
        assert i["attribution"] and i["source_url"] and i["license"] and i["distance_m"] <= 500
    assert len(client.get("/loading-facts", params={"limit": 50}).json()) >= 20


def test_rank_tiers_follow_the_ranks_table(client):
    with psycopg.connect(settings.database_url) as c:
        db = c.execute("SELECT rank, name, discount_pct FROM ranks ORDER BY rank").fetchall()
    tiers = client.get("/rank-tiers", headers=AUTH).json()
    assert [(t["rank"], t["name"], t["discount_pct"]) for t in tiers] == [tuple(r) for r in db]
    assert tiers[-1]["free_item"] is True
