"""Source adapters. Each yields dicts shaped like content_items rows (no DB access here).
Official APIs and bulk downloads only. No images are downloaded (URLs only). Short factual fields only."""
import json
import re
from pathlib import Path

from .http import Fetcher

SEED = Path(__file__).resolve().parents[1] / "data" / "seed"

SOURCES = {
    "analyze-boston": dict(
        name="Analyze Boston (City of Boston open data)", url="https://data.boston.gov",
        license="Open Data Commons Public Domain Dedication and License (PDDL)",
        attribution="Contains data from Analyze Boston, City of Boston (PDDL).", commercial_ok=True,
        notes="CKAN API https://data.boston.gov/api/3"),
    "digital-commonwealth": dict(
        name="Digital Commonwealth", url="https://www.digitalcommonwealth.org",
        license="Per item; only items whose rights statement says no known restrictions or public domain are kept",
        attribution="Digital Commonwealth and the contributing institution; see each item's link.",
        commercial_ok=True, notes="Official JSON API search.json"),
    "freedom-trail-seed": dict(
        name="Freedom Trail (hand-written by the T-Quest team)", url="https://www.thefreedomtrail.org",
        license="Original short text by the T-Quest team",
        attribution="Written by the T-Quest team. Verify before publishing.",
        commercial_ok=True, notes="Facts need a human check; site names are public facts."),
}


def centroid(wkt):
    if not wkt:
        return None
    nums = [float(x) for x in re.findall(r"-?\d+\.\d+", wkt)]
    pts = list(zip(nums[0::2], nums[1::2]))
    if not pts:
        return None
    lon = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    return (lat, lon) if 41 < lat < 43 and -72 < lon < -70 else None


def analyze_boston(f: Fetcher):
    base = "https://data.boston.gov/api/3/action/datastore_search"
    jobs = [
        ("landmark", "fb53d967-ead6-4b4e-ab17-506521434038", "boston-landmarks-commission-blc-landmarks"),
        ("historic-district", "d3400713-ac2f-4a2b-93c7-28463c539903",
         "boston-landmarks-commission-blc-historic-districts"),
    ]
    for category, rid, pkg in jobs:
        offset = 0
        while True:
            res = f.get_json(base, {"resource_id": rid, "limit": 500, "offset": offset})["result"]
            for r in res["records"]:
                name = (r.get("Common_Name") or r.get("Name") or r.get("District_Name") or "").strip()
                c = centroid(r.get("shape_wkt"))
                if not name or c is None or str(r.get("Demolished", "")).lower() == "yes":
                    continue
                desc = " ".join(x for x in [r.get("Status"), r.get("Neighborhood")] if x)
                yield dict(source_id="analyze-boston", external_id=f"{pkg}:{r['_id']}",
                           source_url=f"https://data.boston.gov/dataset/{pkg}", title=name.strip(),
                           short_description=desc or None, category=category, lat=c[0], lon=c[1])
            offset += 500
            if offset >= res["total"]:
                break


OPEN_RIGHTS = ("no known copyright restrictions", "no known us copyright restrictions", "public domain")
CLOSED_HINTS = ("noncommercial", "non-commercial", "all rights reserved", "not evaluated", "undetermined", "under copyright")


def _txt(v):
    return " ".join(v) if isinstance(v, list) else str(v or "")


def digital_commonwealth(f: Fetcher, pages: int = 5, per_page: int = 50):
    """Items whose rights statement clearly says no known restrictions / public domain. Link only, no images."""
    for page in range(1, pages + 1):
        d = f.get_json("https://www.digitalcommonwealth.org/search.json",
                       {"q": "Boston", "search_field": "all_fields", "per_page": per_page, "page": page})
        for x in d["data"]:
            a = x["attributes"]
            rights, lic = _txt(a.get("rights_ss")), _txt(a.get("license_ss"))
            both = (rights + " " + lic).lower()
            if not any(k in both for k in OPEN_RIGHTS) or any(k in both for k in CLOSED_HINTS):
                continue
            title = (a.get("title_info_primary_tsi") or "").strip()
            if not title:
                continue
            yield dict(source_id="digital-commonwealth", external_id=x["id"],
                       source_url=f"https://www.digitalcommonwealth.org/search/{x['id']}", title=title,
                       short_description=None, category="archive-item", lat=None, lon=None,
                       license=f"{rights} {lic}".strip()[:200])


def freedom_trail():
    for t in json.loads((SEED / "freedom_trail.json").read_text(encoding="utf-8")):
        yield dict(source_id="freedom-trail-seed", external_id=t["id"],
                   source_url="https://www.thefreedomtrail.org", title=t["name"],
                   short_description=t["blurb"], category="freedom-trail", lat=t["lat"], lon=t["lon"],
                   needs_verify=True)
