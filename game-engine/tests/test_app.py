import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# The shared write rate limit (shared/tquest_http.py, default 60 a minute) is read once, when the app
# is imported. Every test request comes from the same test client address, so a full run would hit it.
# Raise it for tests only; the running service keeps its own RATE_WRITE_PER_MIN.
os.environ.setdefault("RATE_WRITE_PER_MIN", "100000")

try:
    from fastapi.testclient import TestClient
    from game_engine import app as appmod
    from game_engine.store import MemoryStore
    HAVE_WEB = True
except ImportError:  # web libraries not installed: skip these tests
    HAVE_WEB = False

PARK = {"stop_id": "park", "lat": 42.3564, "lon": -71.0624, "client_time": "2026-11-21T12:00:00"}


def H(user):
    return {"Authorization": "Bearer " + user}


@unittest.skipUnless(HAVE_WEB, "fastapi not installed")
class AppTests(unittest.TestCase):
    def setUp(self):
        appmod.set_store(MemoryStore())
        self.c = TestClient(appmod.app)

    def test_cors_preflight_and_headers(self):
        """A browser app on another origin can call the API (preflight answers 200 with the allow headers)."""
        origin = "http://localhost:5173"
        pre = self.c.options("/me/rank", headers={
            "Origin": origin, "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type"})
        self.assertEqual(pre.status_code, 200)
        self.assertEqual(pre.headers["access-control-allow-origin"], "*")
        self.assertIn("authorization", pre.headers["access-control-allow-headers"].lower())
        pre2 = self.c.options("/redemptions/verify", headers={
            "Origin": origin, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-store-key,content-type"})
        self.assertEqual(pre2.status_code, 200)
        self.assertIn("x-store-key", pre2.headers["access-control-allow-headers"].lower())
        r = self.c.get("/me/rank", headers={"Origin": origin, **H("ann")})
        self.assertEqual((r.status_code, r.headers["access-control-allow-origin"]), (200, "*"))
        self.assertNotIn("access-control-allow-credentials", r.headers)

    def test_needs_token(self):
        self.assertEqual(self.c.get("/me/points").status_code, 401)

    def test_checkin_flow(self):
        r = self.c.post("/checkins", json=PARK, headers=H("ann"))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["points_awarded"], 20)
        self.assertTrue(r.json()["first_visit"])
        self.assertEqual(self.c.get("/me/points", headers=H("ann")).json()["balance"], 20)
        rk = self.c.get("/me/rank", headers=H("ann")).json()
        self.assertEqual((rk["rank"], rk["name"], rk["points_to_next"]), (1, "Harbor Seal", 480))
        self.assertEqual(self.c.get("/me/collection", headers=H("ann")).json()["stops"], ["park"])

    def test_cooldown_too_far_unknown_consent(self):
        self.c.post("/checkins", json=PARK, headers=H("ann"))
        self.assertEqual(self.c.post("/checkins", json=PARK, headers=H("ann")).status_code, 409)
        far = dict(PARK, lat=43.0)
        self.assertEqual(self.c.post("/checkins", json=far, headers=H("bob")).status_code, 422)
        self.assertEqual(self.c.post("/checkins", json=dict(PARK, stop_id="nope"), headers=H("bob")).status_code, 404)
        self.assertEqual(self.c.post("/checkins", json=dict(PARK, consent=False), headers=H("bob")).status_code, 403)

    def test_quest_completes(self):
        self.c.post("/checkins", json=PARK, headers=H("ann"))
        dt = {"stop_id": "downtown", "lat": 42.3555, "lon": -71.0602, "client_time": "2026-11-21T12:00:00"}
        r = self.c.post("/checkins", json=dt, headers=H("ann")).json()
        self.assertEqual(r["points_awarded"], 20 + 40)

    def test_friends_and_leaderboard(self):
        self.c.post("/checkins", json=PARK, headers=H("ann"))
        self.c.post("/checkins", json=PARK, headers=H("bob"))
        self.assertEqual(self.c.post("/friends", json={"username": "bob"}, headers=H("ann")).status_code, 201)
        self.assertEqual(self.c.post("/friends", json={"username": "bob"}, headers=H("ann")).status_code, 409)
        self.assertEqual(self.c.get("/friends", headers=H("bob")).json()[0]["username"], "ann")
        rows = self.c.get("/leaderboards?scope=friends", headers=H("ann")).json()
        self.assertEqual({r["username"] for r in rows}, {"ann", "bob"})
        self.assertEqual(self.c.get("/leaderboards?scope=line", headers=H("ann")).status_code, 422)

    def test_redemption_flow(self):
        r = self.c.post("/redemptions", json={"offer_id": "o1"}, headers=H("ann"))
        self.assertEqual(r.status_code, 201)
        code = r.json()["code"]
        self.assertEqual(self.c.post("/redemptions", json={"offer_id": "o1"}, headers=H("ann")).status_code, 409)
        self.assertEqual(self.c.post("/redemptions", json={"offer_id": "o2"}, headers=H("ann")).status_code, 403)
        body = {"code": code, "store_id": "s1"}
        self.assertEqual(self.c.post("/redemptions/verify", json=body).status_code, 401)
        ok = self.c.post("/redemptions/verify", json=body, headers={"X-Store-Key": "dev-store-key"})
        self.assertEqual(ok.json()["status"], "claimed")
        again = self.c.post("/redemptions/verify", json=body, headers={"X-Store-Key": "dev-store-key"})
        self.assertEqual(again.status_code, 410)

    def test_too_fast_between_far_check_ins(self):
        """Speed check (server time): park -> harvard (about 5 km) in the same second is refused."""
        harvard = {"stop_id": "harvard", "lat": 42.3736, "lon": -71.1190, "client_time": "2026-11-21T12:00:00"}
        with patch.dict(os.environ, {"SPEED_CHECK": "strict"}):
            self.assertEqual(self.c.post("/checkins", json=PARK, headers=H("cy")).status_code, 201)
            r = self.c.post("/checkins", json=harvard, headers=H("cy"))
            self.assertEqual((r.status_code, r.json()["detail"]), (422, "too_fast"))
            # another rider is not affected
            self.assertEqual(self.c.post("/checkins", json=harvard, headers=H("dee")).status_code, 201)
        # off by default in memory mode
        self.assertEqual(self.c.post("/checkins", json=harvard, headers=H("cy")).status_code, 201)

    def test_gps_quality_fields(self):
        r = self.c.post("/checkins", json=dict(PARK, accuracy_m=80), headers=H("gps1"))
        self.assertEqual((r.status_code, r.json()["detail"]), (422, "poor_gps"))
        same = {"lat": PARK["lat"], "lon": PARK["lon"]}
        r = self.c.post("/checkins", json=dict(PARK, samples=[same, same, same]), headers=H("gps2"))
        self.assertEqual((r.status_code, r.json()["detail"]), (422, "suspicious_gps"))
        jitter = [{"lat": PARK["lat"] + d, "lon": PARK["lon"] - d} for d in (0, 0.00001, 0.00002)]
        ok = self.c.post("/checkins", json=dict(PARK, accuracy_m=12, samples=jitter), headers=H("gps3"))
        self.assertEqual(ok.status_code, 201, ok.text)
        too_many = [same] * 11
        self.assertEqual(self.c.post("/checkins", json=dict(PARK, samples=too_many), headers=H("gps4")).status_code, 422)

    def test_offer_needs_badge(self):
        """o3 needs the Red Line badge: refused until the (fake) Red Line is complete."""
        r = self.c.post("/redemptions", json={"offer_id": "o3"}, headers=H("red"))
        self.assertEqual((r.status_code, r.json()["detail"]), (403, "badge_required"))
        stops = {"alewife": (42.3954, -71.1425), "harvard": (42.3736, -71.1190), "park": (42.3564, -71.0624),
                 "downtown": (42.3555, -71.0602), "south-station": (42.3519, -71.0552)}
        for sid, (lat, lon) in stops.items():
            body = {"stop_id": sid, "lat": lat, "lon": lon, "client_time": "2026-11-21T12:00:00"}
            self.assertEqual(self.c.post("/checkins", json=body, headers=H("red")).status_code, 201)
        self.assertIn("line-red-complete", self.c.get("/me/collection", headers=H("red")).json()["badges"])
        self.assertEqual(self.c.post("/redemptions", json={"offer_id": "o3"}, headers=H("red")).status_code, 201)

    def test_per_user_limit_in_the_store(self):
        from datetime import datetime, timedelta
        from game_engine.redemption import RedemptionError
        st = appmod.get_store()
        st.add_badge("lim", "line-red-complete", datetime(2026, 11, 1), "test")
        offer = st.offer("o3")
        now = datetime(2026, 11, 21, 12)
        st.issue_redemption(user="lim", offer_id="o3", offer=offer, user_rank=1, balance=0, now=now)
        st.issue_redemption(user="lim", offer_id="o3", offer=offer, user_rank=1, balance=0, now=now + timedelta(days=8))
        with self.assertRaises(RedemptionError) as c:
            st.issue_redemption(user="lim", offer_id="o3", offer=offer, user_rank=1, balance=0, now=now + timedelta(days=16))
        self.assertEqual((c.exception.reason, c.exception.http_status), ("per_user_limit", 409))

    def test_spot_visit(self):
        r = self.c.post("/spots/demo-cafe/visit", json={}, headers=H("ann"))
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual((r.json()["spot_id"], r.json()["stop_id"], r.json()["already_visited_today"]),
                         ("demo-cafe", "park", False))
        again = self.c.post("/spots/demo-cafe/visit", headers=H("ann"))
        self.assertEqual((again.status_code, again.json()["already_visited_today"]), (200, True))
        # nearest station is the default; an explicit station must be one of the spot's stations
        self.assertEqual(self.c.post("/spots/demo-bar/visit", headers=H("ann")).json()["stop_id"], "downtown")
        self.assertEqual(self.c.post("/spots/demo-bar/visit", json={"stop_id": "park"}, headers=H("bob")).json()["stop_id"], "park")
        r = self.c.post("/spots/demo-cafe/visit", json={"stop_id": "harvard"}, headers=H("bob"))
        self.assertEqual((r.status_code, r.json()["detail"]), (422, "spot_not_near_stop"))
        self.assertEqual(self.c.post("/spots/nope/visit", headers=H("bob")).status_code, 404)
        self.assertEqual(self.c.post("/spots/demo-cafe/visit").status_code, 401)
        # no points for tapping a spot
        self.assertEqual(self.c.get("/me/points", headers=H("ann")).json()["balance"], 0)


if __name__ == "__main__":
    unittest.main()
