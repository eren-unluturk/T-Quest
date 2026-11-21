"""Database tests. Run only when GE_TEST_DATABASE_URL is set.

Everything happens inside one transaction that is rolled back at the end, so
the shared database is left unchanged.
"""
import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

URL = os.environ.get("GE_TEST_DATABASE_URL")
try:
    import psycopg
    from fastapi.testclient import TestClient
    from game_engine import app as appmod
    from game_engine.pg_store import PgStore
    HAVE = True
except ImportError:
    HAVE = False


def H(user):
    return {"Authorization": "Bearer " + user}


@unittest.skipUnless(URL and HAVE, "set GE_TEST_DATABASE_URL to run database tests")
class PgTests(unittest.TestCase):
    def setUp(self):
        self.conn = psycopg.connect(URL, autocommit=False, connect_timeout=15)
        self.conn.execute("set timezone = 'UTC'")
        self.store = PgStore(self.conn)
        appmod.set_store(self.store)
        self.c = TestClient(appmod.app)
        row = self.conn.execute("select id, lat, lon from stops where location_type = 1 or parent_station is null "
                                "order by id limit 1").fetchone()
        self.stop = {"stop_id": row[0], "lat": row[1], "lon": row[2], "client_time": "2026-11-21T12:00:00"}

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()
        appmod.set_store(None)

    def test_healthz(self):
        self.assertEqual(self.c.get("/healthz").json(), {"ok": True, "store": "postgres"})

    def test_checkin_points_rank_collection(self):
        u = "pytest-ann"
        r = self.c.post("/checkins", json=self.stop, headers=H(u))
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["points_awarded"], 20)
        self.assertEqual(self.c.post("/checkins", json=self.stop, headers=H(u)).status_code, 409)
        self.assertEqual(self.c.get("/me/points", headers=H(u)).json()["balance"], 20)
        self.assertEqual(self.c.get("/me/rank", headers=H(u)).json()["name"], "Harbor Seal")
        self.assertEqual(self.c.get("/me/collection", headers=H(u)).json()["stops"], [self.stop["stop_id"]])
        n = self.conn.execute("select count(*) from rider_events where stop_id=%s and user_id="
                              "(select id from users where username=%s)", (self.stop["stop_id"], u)).fetchone()[0]
        self.assertEqual(n, 1)

    def test_catalog_real_lines(self):
        cat = self.store.catalog()
        self.assertEqual(set(cat.lines), {"line-blue-complete", "line-green-complete", "line-mattapan-complete",
                                          "line-orange-complete", "line-red-complete"})
        self.assertEqual(len(cat.lines["line-green-complete"]), 4)
        self.assertEqual(len(cat.lines["line-red-complete"][0]), 22)

    def test_complete_blue_line_unlocks_badge(self):
        u = "pytest-blue"
        stations = sorted(self.store.catalog().lines["line-blue-complete"][0])
        last = None
        for i, sid in enumerate(stations):
            lat, lon = self.conn.execute("select lat, lon from stops where id=%s", (sid,)).fetchone()
            body = {"stop_id": sid, "lat": lat, "lon": lon, "client_time": "2026-11-21T12:00:00"}
            r = self.c.post("/checkins", json=body, headers=H(u))
            self.assertEqual(r.status_code, 201, r.text)
            if i < len(stations) - 1:
                self.assertNotIn("line-blue-complete", r.json()["badges_unlocked"])
            last = r.json()
        self.assertIn("line-blue-complete", last["badges_unlocked"])
        coll = self.c.get("/me/collection", headers=H(u)).json()
        self.assertIn("line-blue-complete", coll["badges"])
        pts = self.c.get("/me/points", headers=H(u)).json()
        self.assertTrue(any(e["reason"].startswith("complete_line:line-blue") for e in pts["recent"]))

    def test_unknown_stop_and_far(self):
        self.assertEqual(self.c.post("/checkins", json=dict(self.stop, stop_id="nope-nope"),
                                     headers=H("pytest-bob")).status_code, 404)
        self.assertEqual(self.c.post("/checkins", json=dict(self.stop, lat=self.stop["lat"] + 0.05),
                                     headers=H("pytest-bob")).status_code, 422)

    def test_friends_and_leaderboard(self):
        self.c.post("/checkins", json=self.stop, headers=H("pytest-ann"))
        self.assertEqual(self.c.post("/friends", json={"username": "pytest-bob"}, headers=H("pytest-ann")).status_code, 201)
        self.assertEqual(self.c.post("/friends", json={"username": "pytest-ann"}, headers=H("pytest-bob")).status_code, 409)
        self.assertEqual([f["username"] for f in self.c.get("/friends", headers=H("pytest-bob")).json()], ["pytest-ann"])
        rows = self.c.get("/leaderboards?scope=friends", headers=H("pytest-ann")).json()
        self.assertEqual({r["username"] for r in rows}, {"pytest-ann", "pytest-bob"})

    def test_redemption_flow(self):
        offer = self.conn.execute("select id, store_id from offers where active and min_rank <= 1 and store_id is not null "
                                  "and (stock is null or stock > 0) limit 1").fetchone()
        if not offer:
            self.skipTest("no usable offer in the database")
        offer_id, store_id = str(offer[0]), str(offer[1])
        self.conn.execute("update stores set store_key_hash=%s where id=%s",
                          (hashlib.sha256(b"test-key").hexdigest(), store_id))
        r = self.c.post("/redemptions", json={"offer_id": offer_id}, headers=H("pytest-cy"))
        self.assertEqual(r.status_code, 201, r.text)
        code = r.json()["code"]
        self.assertEqual(self.c.post("/redemptions", json={"offer_id": offer_id}, headers=H("pytest-cy")).status_code, 409)
        body = {"code": code, "store_id": store_id}
        self.assertEqual(self.c.post("/redemptions/verify", json=body, headers={"X-Store-Key": "wrong"}).status_code, 401)
        ok = self.c.post("/redemptions/verify", json=body, headers={"X-Store-Key": "test-key"})
        self.assertEqual(ok.json()["status"], "claimed", ok.text)
        self.assertEqual(self.c.post("/redemptions/verify", json=body, headers={"X-Store-Key": "test-key"}).status_code, 410)
        self.assertEqual(self.c.post("/redemptions", json={"offer_id": "not-a-uuid"}, headers=H("pytest-cy")).status_code, 404)


if __name__ == "__main__":
    unittest.main()
