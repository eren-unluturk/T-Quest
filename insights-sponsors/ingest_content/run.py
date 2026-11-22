"""python -m ingest_content.run [--sources analyze-boston,digital-commonwealth,freedom-trail-seed]
Resumable (raw responses cached in data/raw, upserts keyed on source + external id). Prints counts only."""
import argparse
import json
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from insights_sponsors.config import settings  # noqa: E402
from insights_sponsors.repo.ids import slug_to_uuid  # noqa: E402

from . import sources as S  # noqa: E402
from .http import Fetcher  # noqa: E402

LINK_SQL = """
INSERT INTO stop_content (stop_id, content_id, distance_m)
SELECT s.id, c.id, d.dist FROM content_items c
JOIN stops s ON s.lat BETWEEN c.lat - 0.0046 AND c.lat + 0.0046
            AND s.lon BETWEEN c.lon - 0.0063 AND c.lon + 0.0063
CROSS JOIN LATERAL (SELECT 2 * 6371000 * asin(sqrt(
    sin(radians(s.lat - c.lat) / 2) ^ 2 +
    cos(radians(c.lat)) * cos(radians(s.lat)) * sin(radians(s.lon - c.lon) / 2) ^ 2)) AS dist) d
WHERE c.lat IS NOT NULL AND d.dist <= 500
ON CONFLICT (stop_id, content_id) DO UPDATE SET distance_m = EXCLUDED.distance_m
"""


def upsert(cur, item: dict) -> None:
    src = S.SOURCES[item["source_id"]]
    cur.execute(
        """INSERT INTO content_items (source_id, external_id, source_url, title, short_description, category,
             lat, lon, license, attribution, commercial_ok, needs_verify, retrieved_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
           ON CONFLICT (source_id, external_id) DO UPDATE SET title=EXCLUDED.title,
             short_description=EXCLUDED.short_description, lat=EXCLUDED.lat, lon=EXCLUDED.lon,
             license=EXCLUDED.license, retrieved_at=now()""",
        (item["source_id"], item["external_id"], item["source_url"], item["title"],
         item["short_description"], item["category"], item["lat"], item["lon"],
         item.get("license") or src["license"], src["attribution"], src["commercial_ok"],
         item.get("needs_verify", False)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default="freedom-trail-seed,analyze-boston,digital-commonwealth")
    want = ap.parse_args().sources.split(",")
    report: dict = {}
    with psycopg.connect(settings.database_url) as conn:
        cur = conn.cursor()
        for sid, s in S.SOURCES.items():
            cur.execute(
                """INSERT INTO content_sources (id, name, url, license, attribution, commercial_ok, notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name,
                   license=EXCLUDED.license, attribution=EXCLUDED.attribution,
                   commercial_ok=EXCLUDED.commercial_ok""",
                (sid, s["name"], s["url"], s["license"], s["attribution"], s["commercial_ok"], s["notes"]))
        for name in want:
            f = Fetcher(name)
            gens = {"freedom-trail-seed": S.freedom_trail, "analyze-boston": lambda: S.analyze_boston(f), "digital-commonwealth": lambda: S.digital_commonwealth(f)}
            n = 0
            try:
                for item in gens[name]():
                    upsert(cur, item)
                    n += 1
            except RuntimeError as e:  # a failing source must not stop the others
                report[name + "_error"] = str(e)
            report[name] = n
        cur.execute("DELETE FROM content_items WHERE source_id NOT IN (SELECT unnest(%s::text[]))", (list(S.SOURCES),))
        cur.execute("DELETE FROM content_sources WHERE id NOT IN (SELECT unnest(%s::text[]))", (list(S.SOURCES),))
        for ff in json.loads((S.SEED / "fun_facts.json").read_text(encoding="utf-8")):
            cur.execute(
                """INSERT INTO loading_facts (id, body, tags, source_url, attribution, needs_verify)
                   VALUES (%s,%s,%s,NULL,%s,true) ON CONFLICT (id) DO UPDATE SET body=EXCLUDED.body,
                   tags=EXCLUDED.tags""",
                (slug_to_uuid(ff["id"]), ff["body"], ff["tags"],
                 "Written by the T-Quest team. Verify before publishing."))
        cur.execute(LINK_SQL)
        report["stop_content_links"] = cur.execute("SELECT count(*) FROM stop_content").fetchone()[0]
        report["by_source"] = {r[0]: r[1] for r in cur.execute(
            """SELECT c.source_id, count(DISTINCT c.id) || ' items, ' || count(DISTINCT sc.content_id) || ' linked'
               FROM content_items c LEFT JOIN stop_content sc ON sc.content_id = c.id GROUP BY 1""").fetchall()}
    print(json.dumps(report))


if __name__ == "__main__":
    main()
