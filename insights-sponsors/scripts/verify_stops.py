"""Check data/seed/stops.json against the MBTA V3 API (free, no key needed).

For every seeded stop: fetch /stops/{id}, print the seed name vs the API name and
the distance in metres between the seed and API coordinates.

Exit code is non-zero when an id is unknown, a request fails, or (without
--write) a name differs. With --write, names and coordinates in stops.json are
replaced by the API values.

The API allows about 20 requests a minute without a key. Set MBTA_API_KEY in the
environment to raise that; it is sent as x-api-key and never stored.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

BASE = "https://api-v3.mbta.com"
STOPS_FILE = Path(__file__).resolve().parents[1] / "data" / "seed" / "stops.json"
PAUSE_S = 0.3


def haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371000.0 * asin(sqrt(a))


def fetch_stop(stop_id):
    """Return the API attributes, or None when the id is unknown (404)."""
    headers = {"accept": "application/vnd.api+json"}
    if os.environ.get("MBTA_API_KEY"):
        headers["x-api-key"] = os.environ["MBTA_API_KEY"]
    url = f"{BASE}/stops/{urllib.request.quote(stop_id, safe='')}"
    for _ in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                remaining = r.headers.get("x-ratelimit-remaining")
                reset = r.headers.get("x-ratelimit-reset")
                if remaining == "0" and reset:
                    time.sleep(max(0.0, int(reset) - time.time()) + 1)
                return json.load(r)["data"]["attributes"]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429:
                reset = e.headers.get("x-ratelimit-reset")
                wait = max(2.0, int(reset) - time.time() + 1) if reset else 30.0
                print(f"  rate limited, waiting {wait:.0f}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"gave up on {stop_id}: still rate limited")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="update name/lat/lon in stops.json from the API")
    args = ap.parse_args()

    stops = json.loads(STOPS_FILE.read_text(encoding="utf-8"))
    bad = 0
    changed = 0
    print(f"{'id':<16} {'seed name':<34} {'api name':<34} {'dist_m':>7}")
    for stop in stops:
        attrs = fetch_stop(stop["id"])
        time.sleep(PAUSE_S)
        if attrs is None:
            print(f"{stop['id']:<16} {stop['name']:<34} {'UNKNOWN ID':<34} {'-':>7}")
            bad += 1
            continue
        dist = haversine_m(stop["lat"], stop["lon"], attrs["latitude"], attrs["longitude"])
        name_ok = stop["name"] == attrs["name"]
        flag = "" if name_ok else "  NAME DIFFERS"
        print(f"{stop['id']:<16} {stop['name']:<34} {attrs['name']:<34} {dist:>7.1f}{flag}")
        if args.write:
            if not name_ok or dist > 0.5:
                changed += 1
            stop["name"] = attrs["name"]
            stop["lat"] = attrs["latitude"]
            stop["lon"] = attrs["longitude"]
        elif not name_ok:
            bad += 1

    if args.write:
        STOPS_FILE.write_text(json.dumps(stops, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {STOPS_FILE.name}: {changed} of {len(stops)} stops updated")
    print(f"{len(stops)} stops checked, {bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
