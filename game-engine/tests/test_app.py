import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

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
