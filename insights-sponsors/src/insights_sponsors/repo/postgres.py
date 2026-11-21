"""Postgres (Tiger Data) backend for the catalog: stops, offers, physical rewards, nearby spots.

Everything not listed here (consent, place visits, analytics inputs) still comes from the memory
repository this class extends. Label policy: nearby-spot labels are read ONLY from the
`spot_labels_public` view (declared or certified), so pending labels cannot leave the database.
"""
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row

from ..config import settings
from ..models import Offer, PhysicalReward, RewardStore, Stop
from ..spots import CategoryRef, Spot, SpotLabel, public_labels
from .memory import MemoryRepository

EPOCH = datetime(2026, 11, 1, tzinfo=timezone.utc)


class PostgresRepository(MemoryRepository):
    def __init__(self, database_url: str | None = None, **kw):
        super().__init__(**kw)
        self._url = database_url or settings.database_url
        if not self._url:
            raise RuntimeError("DATABASE_URL is not set")

    def _q(self, sql: str, params=None) -> list[dict]:
        with psycopg.connect(self._url, row_factory=dict_row) as conn:
            return conn.execute(sql, params).fetchall()

    # stops
    def get_stop(self, stop_id: str) -> Stop | None:
        rows = self._q(
            "SELECT id, name, lat, lon, coalesce(neighborhood, municipality, '') AS neighborhood, mode "
            "FROM stops WHERE id = %s", (stop_id,))
        if not rows:
            return None
        r = rows[0]
        mode = "bus" if r["mode"] == "bus" else "subway"
        return Stop(id=r["id"], name=r["name"], lat=r["lat"] or 0.0, lon=r["lon"] or 0.0,
                    neighborhood=r["neighborhood"], mode=mode)

    # offers
    def offers(self, stop_id=None, store_id=None, category=None) -> list[Offer]:
        sql = """
        SELECT o.id, o.sponsor_id, o.store_id, coalesce(o.title,'') AS title,
               coalesce(o.description,'') AS description, o.kind, o.discount_pct, o.points_cost,
               coalesce(o.min_rank,1) AS min_rank, o.required_badge_id,
               coalesce(o.per_user_limit,1) AS per_user_limit, o.starts_at, o.ends_at,
               coalesce(o.placement,'local_pick') AS placement, sp.demo_placeholder AS demo
          FROM offers o
          JOIN sponsors sp ON sp.id = o.sponsor_id
          LEFT JOIN stores st ON st.id = o.store_id
         WHERE o.active AND coalesce(sp.active, true)
           AND (%(store)s::uuid IS NULL OR o.store_id = %(store)s::uuid)
           AND (%(cat)s::text IS NULL OR coalesce(st.category, sp.category) = %(cat)s::text)
           AND (%(stop)s::text IS NULL OR st.nearest_stop_id = %(stop)s::text OR EXISTS (
                 SELECT 1 FROM nearby_spots ns JOIN spot_stop_links l ON l.spot_id = ns.id
                  WHERE ns.sponsor_id = o.sponsor_id AND ns.active AND ns.removed_at IS NULL
                    AND l.stop_id = %(stop)s::text))
         ORDER BY o.min_rank, o.title"""
        out = []
        for r in self._q(sql, {"store": store_id, "cat": category, "stop": stop_id}):
            kind = r["kind"] if r["kind"] in ("discount", "free_item", "points_item") else "discount"
            out.append(Offer(
                id=str(r["id"]), sponsor_id=str(r["sponsor_id"]),
                store_id=str(r["store_id"]) if r["store_id"] else None, title=r["title"],
                description=r["description"], kind=kind, discount_pct=r["discount_pct"],
                points_cost=r["points_cost"] or None, min_rank=min(max(r["min_rank"], 1), 5),
                required_badge_id=r["required_badge_id"], per_user_limit=r["per_user_limit"],
                starts_at=r["starts_at"] or EPOCH, ends_at=r["ends_at"], placement=r["placement"],
                demo=r["demo"]))
        return out

    # physical rewards
    def physical_rewards(self) -> list[PhysicalReward]:
        inv: dict = {}
        for r in self._q("SELECT store_id, physical_reward_id, stock FROM store_inventory ORDER BY store_id"):
            inv.setdefault(r["physical_reward_id"], []).append(
                RewardStore(store_id=str(r["store_id"]), in_stock=r["stock"] > 0))
        rows = self._q(
            "SELECT id, item_type, name, coalesce(description,'') AS description, badge_id, "
            "coalesce(min_rank,1) AS min_rank, coalesce(per_user_limit,1) AS per_user_limit, image_url "
            "FROM physical_rewards WHERE active AND item_type IN ('sticker','patch') ORDER BY name")
        return [PhysicalReward(id=str(r["id"]), kind=r["item_type"], name=r["name"],
                               description=r["description"], badge_id=r["badge_id"],
                               min_rank=r["min_rank"], per_user_limit=r["per_user_limit"],
                               image_url=r["image_url"], stores=inv.get(r["id"], []))
                for r in rows]

    # nearby spots
    def spot_categories(self) -> list[CategoryRef]:
        return [CategoryRef(slug=r["slug"], display_name=r["display_name"])
                for r in self._q("SELECT slug, display_name FROM spot_categories ORDER BY sort_order, slug")]

    def label_types(self) -> list[dict]:
        return [dict(r) for r in self._q(
            "SELECT slug, display_name FROM label_types ORDER BY sort_order, slug")]

    def _spots(self, where: str, params: dict) -> list[Spot]:
        rows = self._q(f"""
            SELECT s.id, s.name, s.category_slug, c.display_name AS category_name, s.address, s.lat, s.lon,
                   s.demo_placeholder, s.sponsor_id, s.placement_type, s.source,
                   {'l.distance_m' if 'stop' in params else 'NULL::float8 AS distance_m'}
              FROM nearby_spots s JOIN spot_categories c ON c.slug = s.category_slug
              {'JOIN spot_stop_links l ON l.spot_id = s.id' if 'stop' in params else ''}
             WHERE s.active AND s.removed_at IS NULL AND {where}""", params)
        if not rows:
            return []
        ids = [r["id"] for r in rows]
        labels: dict = {}
        for r in self._q(
            """SELECT p.spot_id, p.label_slug, t.display_name, p.status, p.evidence_url, p.declaration_note,
                      p.verified_at, p.verified_by
                 FROM spot_labels_public p JOIN label_types t ON t.slug = p.label_slug
                WHERE p.spot_id = ANY(%s) ORDER BY t.sort_order""", (ids,)):
            labels.setdefault(r["spot_id"], []).append(SpotLabel(
                slug=r["label_slug"], display_name=r["display_name"], status=r["status"],
                evidence_url=r["evidence_url"], declaration_note=r["declaration_note"],
                verified_at=r["verified_at"], verified_by=r["verified_by"]))
        all_offers = None
        out = []
        for r in rows:
            offers = []
            if r["sponsor_id"]:
                all_offers = all_offers if all_offers is not None else self.offers()
                offers = [o for o in all_offers if o.sponsor_id == str(r["sponsor_id"])]
            out.append(public_labels(Spot(
                id=str(r["id"]), name=r["name"],
                category=CategoryRef(slug=r["category_slug"], display_name=r["category_name"]),
                address=r["address"], lat=r["lat"], lon=r["lon"], placement_type=r["placement_type"],
                demo=r["demo_placeholder"], sponsor_id=str(r["sponsor_id"]) if r["sponsor_id"] else None,
                distance_m=r["distance_m"], source=r["source"], labels=labels.get(r["id"], []),
                offers=offers)))
        return out

    def spots_for_stop(self, stop_id: str) -> list[Spot]:
        return self._spots("l.stop_id = %(stop)s", {"stop": stop_id})

    def get_spot(self, spot_id: str) -> Spot | None:
        try:
            rows = self._spots("s.id = %(id)s::uuid", {"id": spot_id})
        except psycopg.errors.InvalidTextRepresentation:
            return None
        return rows[0] if rows else None
