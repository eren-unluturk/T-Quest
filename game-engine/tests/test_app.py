import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from fastapi.testclient import TestClient
    from game_engine import app as appmod
    HAVE_WEB = True
except ImportError:  # web libraries not installed: skip these tests
    HAVE_WEB = False

PARK = {"stop_id": "park", "lat": 42.3564, "lon": -71.0624, "client_time": "2026-11-21T12:00:00"}


def H(user):
    return {"Authorization": "Bearer " + user}


@unittest.skipUnless(HAVE_WEB, "fastapi not installed")
class AppTests(unittest.TestCase):
    def setUp(self):
        appmod.reset()
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


if __name__ == "__main__":
    unittest.main()
