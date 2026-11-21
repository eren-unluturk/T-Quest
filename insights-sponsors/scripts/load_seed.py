"""Idempotent upsert of the catalog and nearby-spot seed into the shared Tiger Data database.

Run from insights-sponsors/:  python scripts/load_seed.py
Writes only: badges (missing slugs), sponsors, stores, offers, physical_rewards, store_inventory,
spot_categories, label_types, nearby_spots, spot_stop_links, spot_labels. Never touches MBTA tables.
Ids are uuid5(slug), so running twice gives identical counts. Prints counts only, never the URL.
"""
import json
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from insights_sponsors.config import settings  # noqa: E402
from insights_sponsors.repo.ids import slug_to_uuid as u  # noqa: E402

SEED = ROOT / "data" / "seed"


def load(name):
    return json.loads((SEED / name).read_text(encoding="utf-8"))


def badge_kind(slug: str) -> str:
    if slug.startswith("line-"):
        return "line_complete"
    if slug.startswith("rank-"):
        return "rank"
    return "trail"


def run(conn) -> dict:
    counts: dict[str, int] = {}
    cur = conn.cursor()
    sponsors, stores, offers = load("sponsors.json"), load("stores.json"), load("offers.json")
    rewards, spots = load("physical_rewards.json"), load("spots.json")
    existing_stops = {r[0] for r in cur.execute("SELECT id FROM stops").fetchall()}

    badges = {r["badge_id"] for r in rewards} | {o["required_badge_id"] for o in offers if o["required_badge_id"]}
    for b in sorted(badges):
        cur.execute(
            "INSERT INTO badges (id, name, kind) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (b, b.replace("-", " ").title(), badge_kind(b)),
        )
    for s in sponsors:
        cur.execute(
            """INSERT INTO sponsors (id, name, category, demo_placeholder) VALUES (%s,%s,%s,%s)
               ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, category=EXCLUDED.category,
               demo_placeholder=EXCLUDED.demo_placeholder""",
            (u(s["id"]), s["name"], s.get("category", "other"), s.get("demo_placeholder", True)),
        )
    counts["sponsors"] = len(sponsors)

    sponsor_of_store = {o["store_id"]: o["sponsor_id"] for o in offers if o["store_id"]}
    n = 0
    for st in stores:
        if st["id"] not in sponsor_of_store or st["nearest_stop_id"] not in existing_stops:
            continue
        cur.execute(
            """INSERT INTO stores (id, sponsor_id, name, address, lat, lon, nearest_stop_id, category, demo_placeholder)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,true)
               ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, address=EXCLUDED.address, lat=EXCLUDED.lat,
               lon=EXCLUDED.lon, nearest_stop_id=EXCLUDED.nearest_stop_id, category=EXCLUDED.category""",
            (u(st["id"]), u(sponsor_of_store[st["id"]]), st["name"], st["address"], st["lat"], st["lon"],
             st["nearest_stop_id"], st["category"]),
        )
        n += 1
    counts["stores"] = n

    for o in offers:
        cur.execute(
            """INSERT INTO offers (id, sponsor_id, store_id, title, description, kind, min_rank, points_cost,
                 discount_pct, required_badge_id, per_user_limit, placement, starts_at, ends_at, active)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true)
               ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title, description=EXCLUDED.description,
                 kind=EXCLUDED.kind, min_rank=EXCLUDED.min_rank, points_cost=EXCLUDED.points_cost,
                 discount_pct=EXCLUDED.discount_pct, required_badge_id=EXCLUDED.required_badge_id,
                 per_user_limit=EXCLUDED.per_user_limit, placement=EXCLUDED.placement""",
            (u(o["id"]), u(o["sponsor_id"]), u(o["store_id"]) if o["store_id"] else None, o["title"],
             o["description"], o["kind"], o["min_rank"], o["points_cost"] or 0, o["discount_pct"],
             o["required_badge_id"], o["per_user_limit"], o["placement"], o["starts_at"], o["ends_at"]),
        )
    counts["offers"] = len(offers)

    inv = 0
    for r in rewards:
        cur.execute(
            """INSERT INTO physical_rewards (id, name, item_type, badge_id, min_rank, per_user_limit, description)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, item_type=EXCLUDED.item_type,
                 badge_id=EXCLUDED.badge_id, min_rank=EXCLUDED.min_rank,
                 per_user_limit=EXCLUDED.per_user_limit, description=EXCLUDED.description""",
            (u(r["id"]), r["name"], r["kind"], r["badge_id"], r["min_rank"], r["per_user_limit"], r["description"]),
        )
        for rs in r["stores"]:
            if rs["store_id"] not in sponsor_of_store:
                continue
            cur.execute(
                """INSERT INTO store_inventory (store_id, physical_reward_id, stock) VALUES (%s,%s,%s)
                   ON CONFLICT (store_id, physical_reward_id) DO NOTHING""",
                (u(rs["store_id"]), u(r["id"]), 10 if rs["in_stock"] else 0),  # placeholder stock
            )
            inv += 1
    counts["physical_rewards"] = len(rewards)
    counts["store_inventory"] = inv

    for i, (slug, name) in enumerate(spots["categories"]):
        cur.execute(
            "INSERT INTO spot_categories (slug, display_name, sort_order) VALUES (%s,%s,%s) "
            "ON CONFLICT (slug) DO NOTHING", (slug, name, (i + 1) * 10))
    for i, (slug, name) in enumerate(spots["label_types"]):
        cur.execute(
            "INSERT INTO label_types (slug, display_name, sort_order) VALUES (%s,%s,%s) "
            "ON CONFLICT (slug) DO NOTHING", (slug, name, (i + 1) * 10))

    links = labels = 0
    for sp in spots["spots"]:
        cur.execute(
            """INSERT INTO nearby_spots (id, name, category_slug, address, lat, lon, demo_placeholder,
                 sponsor_id, placement_type, active, source) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, category_slug=EXCLUDED.category_slug,
                 address=EXCLUDED.address, demo_placeholder=EXCLUDED.demo_placeholder,
                 sponsor_id=EXCLUDED.sponsor_id, placement_type=EXCLUDED.placement_type,
                 active=EXCLUDED.active, source=EXCLUDED.source""",
            (u(sp["id"]), sp["name"], sp["category"], sp["address"], sp["lat"], sp["lon"],
             sp["demo_placeholder"], u(sp["sponsor_id"]) if sp["sponsor_id"] else None,
             sp["placement_type"], sp["active"], sp["source"]),
        )
        for link in sp["stops"]:
            if link["stop_id"] not in existing_stops:
                raise SystemExit(f"stop {link['stop_id']} missing from stops; load MBTA static data first")
            cur.execute(
                """INSERT INTO spot_stop_links (spot_id, stop_id, distance_m) VALUES (%s,%s,%s)
                   ON CONFLICT (spot_id, stop_id) DO UPDATE SET distance_m=EXCLUDED.distance_m""",
                (u(sp["id"]), link["stop_id"], link["distance_m"]),
            )
            links += 1
        for lb in sp["labels"]:
            cur.execute(
                """INSERT INTO spot_labels (spot_id, label_slug, status, evidence_url, declaration_note,
                     verified_at, verified_by) VALUES (%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (spot_id, label_slug) DO UPDATE SET status=EXCLUDED.status,
                     evidence_url=EXCLUDED.evidence_url, declaration_note=EXCLUDED.declaration_note,
                     verified_at=EXCLUDED.verified_at, verified_by=EXCLUDED.verified_by""",
                (u(sp["id"]), lb["label"], lb["status"], lb["evidence_url"], lb["declaration_note"],
                 lb["verified_at"], lb["verified_by"]),
            )
            labels += 1
    counts["nearby_spots"] = len(spots["spots"])
    counts["spot_stop_links"] = links
    counts["spot_labels"] = labels
    return counts


def main() -> None:
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set")
    with psycopg.connect(settings.database_url) as conn:
        counts = run(conn)
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
