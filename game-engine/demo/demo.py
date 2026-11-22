"""Walk through the game-engine API with fake data and print what happens.

Run from the repo root:
    python game-engine/demo/demo.py                 # in-process, no server, no database
    python game-engine/demo/demo.py --url http://127.0.0.1:8003
        (a server started WITHOUT DATABASE_URL, so nothing real is written)

Uses the in-memory demo data: stops park, downtown, harvard, alewife and
south-station; a downtown quest; offers o1 (rank 1) and o2 (rank 5).
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

STOPS = {  # lat, lon of the fake demo stops
    "park": (42.3564, -71.0624), "downtown": (42.3555, -71.0602), "harvard": (42.3736, -71.1190),
    "alewife": (42.3954, -71.1425), "south-station": (42.3519, -71.0552),
}
STORE_KEY = {"X-Store-Key": "dev-store-key"}


def make_client(url):
    if url:
        import httpx
        return httpx.Client(base_url=url, timeout=15)
    from fastapi.testclient import TestClient
    from game_engine import app as appmod
    from game_engine.store import MemoryStore
    appmod.set_store(MemoryStore())
    return TestClient(appmod.app)


def show(title):
    print("\n" + "=" * 70 + "\n" + title + "\n" + "=" * 70)


def call(c, method, path, user=None, body=None, headers=None, note=""):
    h = dict(headers or {})
    if user:
        h["Authorization"] = "Bearer " + user
    r = c.request(method, path, json=body, headers=h)
    try:
        data = r.json()
    except ValueError:
        data = r.text
    text = json.dumps(data, default=str)
    if len(text) > 230:
        text = text[:230] + " ..."
    print(f"{method:4} {path}  [{user or 'store'}]  ->  {r.status_code}  {text}" + (f"   <- {note}" if note else ""))
    return r


def checkin(c, user, stop, note="", **over):
    lat, lon = STOPS.get(stop, (42.0, -71.0))
    body = {"stop_id": stop, "lat": lat, "lon": lon, "client_time": "2026-11-21T12:00:00"}
    body.update(over)
    return call(c, "POST", "/checkins", user, body, note=note)


def main(argv):
    url = argv[argv.index("--url") + 1] if "--url" in argv else None
    c = make_client(url)

    show("0. The service is up")
    call(c, "GET", "/healthz")

    show("1. Ann starts at Harbor Seal with 0 points")
    call(c, "GET", "/me/rank", "ann")

    show("2. Ann checks in: first visits pay 20, the downtown quest pays 40 more")
    checkin(c, "ann", "park", "first visit: 20 points")
    checkin(c, "ann", "downtown", "20 + the 'Downtown loop' quest (park + downtown) = 60")

    show("3. Things that must be refused")
    checkin(c, "ann", "park", "409: checked in at park less than 30 minutes ago")
    checkin(c, "ann", "harvard", "422: phone is far from the stop", lat=43.0)
    checkin(c, "ann", "harvard", "403: no location consent", consent=False)
    checkin(c, "ann", "nowhere", "404: unknown stop")
    call(c, "GET", "/me/points", None, note="401: no sign-in")

    show("4. Ann finishes the (fake) Red Line: harvard, alewife, south-station")
    checkin(c, "ann", "harvard")
    checkin(c, "ann", "alewife")
    r = checkin(c, "ann", "south-station", "Red Line complete: badge + 300 bonus points")
    call(c, "GET", "/me/collection", "ann", note="stops, badges and stickers earned")
    call(c, "GET", "/me/points", "ann")
    call(c, "GET", "/me/rank", "ann", note="points_to_next shows the climb to Town Crier")

    show("5. Friends and leaderboards")
    checkin(c, "bob", "park")
    call(c, "POST", "/friends", "ann", {"username": "bob"})
    call(c, "POST", "/friends", "ann", {"username": "bob"}, note="409: already friends")
    call(c, "GET", "/friends", "ann")
    call(c, "GET", "/leaderboards?scope=global&period=week", "ann")
    call(c, "GET", "/leaderboards?scope=friends", "bob")

    show("6. Quests")
    call(c, "GET", "/quests", "ann")

    show("6b. Tapping a spot saves one visit event (no points), once a day")
    call(c, "POST", "/spots/demo-cafe/visit", "ann", {}, note="201: first tap today")
    call(c, "POST", "/spots/demo-cafe/visit", "ann", {}, note="200: already visited today, nothing new written")
    call(c, "POST", "/spots/demo-cafe/visit", "ann", {"stop_id": "harvard"}, note="422: that spot is not near harvard")

    if not url:
        show("6c. Speed check (on by default with the database; switched on here): park then harvard in one second")
        os.environ["SPEED_CHECK"] = "strict"
        checkin(c, "cy", "park", "first check-in")
        checkin(c, "cy", "harvard", "422 too_fast: about 5 km in one second")
        os.environ.pop("SPEED_CHECK")

    show("7. Redeeming a reward: single-use code, checked at the store")
    red = call(c, "POST", "/redemptions", "ann", {"offer_id": "o1"}, note="rank 1 is enough for o1")
    code = red.json().get("code")
    call(c, "POST", "/redemptions", "ann", {"offer_id": "o1"}, note="409: one per store per week")
    call(c, "POST", "/redemptions", "ann", {"offer_id": "o2"}, note="403: o2 needs rank 5")
    call(c, "POST", "/redemptions/verify", None, {"code": code, "store_id": "s1"}, note="401: no store key")
    call(c, "POST", "/redemptions/verify", None, {"code": code, "store_id": "s1"}, STORE_KEY, "the store scans the code: claimed")
    call(c, "POST", "/redemptions/verify", None, {"code": code, "store_id": "s1"}, STORE_KEY, "410: a code works once")

    print("\nDone. Open /docs on a running server to try every call by hand.")


if __name__ == "__main__":
    main(sys.argv[1:])
