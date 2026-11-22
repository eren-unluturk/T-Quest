"""Database tests. Run only when GE_TEST_DATABASE_URL is set.

Everything happens inside one transaction that is rolled back at the end, so
the shared database is left unchanged.
"""
import hashlib
import os
import sys
import unittest
from unittest.mock import patch

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
        self.env = patch.dict(os.environ, {"VEHICLE_CHECK": "off", "SPEED_CHECK": "off"})
        self.env.start()
        self.store = PgStore(self.conn, allow_writes=True)
        appmod.set_store(self.store)
        self.c = TestClient(appmod.app)
        row = self.conn.execute("select id, lat, lon from stops where location_type = 1 or parent_station is null "
                                "order by id limit 1").fetchone()
        self.stop = {"stop_id": row[0], "lat": row[1], "lon": row[2], "client_time": "2026-11-21T12:00:00"}

    def tearDown(self):
        self.env.stop()
        self.conn.rollback()
        self.conn.close()
        appmod.set_store(None)

    def test_healthz(self):
        self.assertEqual(self.c.get("/healthz").json(), {"ok": True, "store": "postgres", "writes": True})

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
                              "(select id from users where username=%s)", (self.stop["stop_id"], "demo_" + u)).fetchone()[0]
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

    def test_delay_job_pays_once(self):
        from game_engine import delay_job
        self.conn.execute("insert into users (username, home_line_override) values ('demo_pytest-rider', 'Red')")
        self.conn.execute("insert into users (username, home_line_override) values ('demo_pytest-green', 'Green-B')")
        self.conn.execute("insert into alerts (id, effect, active_start) values ('pytest-alert', 'NO_SERVICE', now() - interval '1 hour')")
        self.conn.execute("insert into alerts (id, effect, active_start) values ('pytest-minor', 'DELAY', now() - interval '1 hour')")
        self.conn.execute("insert into alert_entities (alert_id, route_id) values ('pytest-alert', 'Red')")
        self.conn.execute("insert into alert_entities (alert_id, route_id) values ('pytest-minor', 'Green-B')")
        before = delay_job.run(self.conn, dry_run=True, allow_writes=False)
        self.assertGreaterEqual(before["paid"], 1)
        first = delay_job.run(self.conn, allow_writes=True)
        self.assertGreaterEqual(first["paid"], 1)
        def paid(alert_id):
            return self.conn.execute(
                "select count(*), coalesce(sum(delta), 0) from points_ledger where ref_type='alert' and ref_id=%s "
                "and reason='delay_compensation'", (alert_id,)).fetchone()

        self.assertEqual(paid("pytest-alert"), (1, 50))   # Red home-line rider, once
        self.assertEqual(paid("pytest-minor"), (0, 0))    # a plain DELAY pays nothing
        second = delay_job.run(self.conn, allow_writes=True)
        self.assertEqual(second["paid"], 0)               # nothing new on a second run
        self.assertEqual(paid("pytest-alert"), (1, 50))
    def test_live_vehicle_check(self):
        """Default mode needs a live vehicle near the stop; a stop with none is refused."""
        near = self.conn.execute(
            "select s.id, s.lat, s.lon from stops s join vehicles v on abs(v.lat - s.lat) < 0.001 "
            "and abs(v.lon - s.lon) < 0.001 where v.time > now() - interval '2 minutes' limit 1").fetchone()
        far = self.conn.execute(
            "select s.id, s.lat, s.lon from stops s where not exists (select 1 from vehicles v "
            "where v.time > now() - interval '15 minutes' and abs(v.lat - s.lat) < 0.02 "
            "and abs(v.lon - s.lon) < 0.02) limit 1").fetchone()
        with patch.dict(os.environ, {"VEHICLE_CHECK": "strict"}):
            if near:
                body = {"stop_id": near[0], "lat": near[1], "lon": near[2], "client_time": "2026-11-21T12:00:00"}
                self.assertEqual(self.c.post("/checkins", json=body, headers=H("pytest-v1")).status_code, 201)
            if far:
                body = {"stop_id": far[0], "lat": far[1], "lon": far[2], "client_time": "2026-11-21T12:00:00"}
                r = self.c.post("/checkins", json=body, headers=H("pytest-v2"))
                self.assertEqual((r.status_code, r.json()["detail"]), (422, "no_vehicle"))
        if not near and not far:
            self.skipTest("no live vehicle data")

    def test_physical_rewards_come_from_the_table(self):
        ids = ["line-red-complete", "freedom-trail", "rank-3", "no-such-badge"]
        expected = sorted({r[0] for r in self.conn.execute(
            "select name from physical_rewards where active and badge_id = any(%s)", (ids,)).fetchall()})
        got = self.store.physical_rewards_for(ids)
        self.assertEqual(got, expected)
        self.assertEqual(len(got), len(set(got)))   # no duplicates
        self.assertEqual(self.store.physical_rewards_for([]), [])

    def test_spots_near_stops_quest(self):
        """Community quest: any 3 stations that have a nearby spot (rolled back)."""
        stations = [r[0] for r in self.conn.execute(
            "select distinct l.stop_id from spot_stop_links l join nearby_spots s on s.id = l.spot_id "
            "where s.active and s.removed_at is null order by 1").fetchall()]
        if len(stations) < 3:
            self.skipTest("fewer than 3 stations have spots")
        self.conn.execute("delete from quests")   # inside the rolled-back transaction: start from no quests
        self.conn.execute("insert into badges (id, name, kind) values ('local-explorer', 'Local Explorer', 'event') "
                          "on conflict (id) do nothing")
        self.conn.execute("insert into quests (title, goal, criteria, reward_points, reward_badge_id) values "
                          "('pytest local explorer', 'Visit 3 stations with spots', "
                          "'{\"type\": \"spots_near_stops\", \"min_stops\": 3}'::jsonb, 40, 'local-explorer')")
        u = "pytest-explorer"
        results = []
        for sid in stations[:3]:
            lat, lon = self.conn.execute("select lat, lon from stops where id=%s", (sid,)).fetchone()
            body = {"stop_id": sid, "lat": lat, "lon": lon, "client_time": "2026-11-21T12:00:00"}
            r = self.c.post("/checkins", json=body, headers=H(u))
            self.assertEqual(r.status_code, 201, r.text)
            results.append(r.json())
        self.assertNotIn("local-explorer", results[0]["badges_unlocked"])
        self.assertNotIn("local-explorer", results[1]["badges_unlocked"])
        self.assertIn("local-explorer", results[2]["badges_unlocked"])
        self.assertEqual(results[2]["points_awarded"], 20 + 40)
        # a fourth visit does not pay the quest twice
        if len(stations) > 3:
            sid = stations[3]
            lat, lon = self.conn.execute("select lat, lon from stops where id=%s", (sid,)).fetchone()
            r = self.c.post("/checkins", json={"stop_id": sid, "lat": lat, "lon": lon,
                                              "client_time": "2026-11-21T12:00:00"}, headers=H(u))
            self.assertEqual(r.json()["points_awarded"], 20)   # only the normal first-visit points, no second 40
        goal = [q["goal"] for q in self.c.get("/quests", headers=H(u)).json() if q["title"] == "pytest local explorer"]
        self.assertEqual(goal, ["Visit 3 different stations"])

    def test_complete_freedom_trail_unlocks_badge(self):
        stations = sorted(self.store.catalog().trail)
        if len(stations) < 2:
            self.skipTest("Freedom Trail stations are not loaded")
        u = "pytest-trail"
        last = None
        for i, sid in enumerate(stations):
            lat, lon = self.conn.execute("select lat, lon from stops where id=%s", (sid,)).fetchone()
            body = {"stop_id": sid, "lat": lat, "lon": lon, "client_time": "2026-11-21T12:00:00"}
            r = self.c.post("/checkins", json=body, headers=H(u))
            self.assertEqual(r.status_code, 201, r.text)
            if i < len(stations) - 1:
                self.assertNotIn("freedom-trail", r.json()["badges_unlocked"])
            last = r.json()
        self.assertIn("freedom-trail", last["badges_unlocked"])
        rewards = self.c.get("/me/collection", headers=H(u)).json()["physical_rewards"]
        self.assertIn("Freedom Trail sticker", rewards)

    def test_read_only_by_default(self):
        """No GE_ALLOW_DB_WRITES: GET works, every write is refused, no user row is created."""
        appmod.set_store(PgStore(self.conn))   # allow_writes defaults to False
        self.assertEqual(self.c.get("/healthz").json()["writes"], False)
        self.assertEqual(self.c.get("/me/points", headers=H("pytest-ro")).json()["balance"], 0)
        self.assertEqual(self.c.get("/me/rank", headers=H("pytest-ro")).json()["name"], "Harbor Seal")
        for method, path, body in [("post", "/checkins", self.stop), ("post", "/friends", {"username": "x"}),
                                   ("post", "/redemptions", {"offer_id": "o"}),
                                   ("post", "/redemptions/verify", {"code": "c", "store_id": "s"}),
                                   ("post", "/spots/00000000-0000-0000-0000-000000000000/visit", {})]:
            r = getattr(self.c, method)(path, json=body, headers=H("pytest-ro"))
            self.assertEqual((r.status_code, r.json()["detail"]), (503, "db_writes_disabled"), path)
        n = self.conn.execute("select count(*) from users where username like 'demo_pytest-ro%'").fetchone()[0]
        self.assertEqual(n, 0)

    def test_demo_rows_are_flagged_and_reset_removes_them(self):
        from game_engine import demo_reset
        u = "pytest-flag"
        self.assertEqual(self.c.post("/checkins", json=self.stop, headers=H(u)).status_code, 201)
        self.c.post("/friends", json={"username": "pytest-flag2"}, headers=H(u))
        # flags: demo username, synthetic rider event
        self.assertEqual(self.conn.execute("select count(*) from users where username = 'demo_pytest-flag'").fetchone()[0], 1)
        self.assertEqual(self.conn.execute(
            "select bool_and(is_synthetic), count(*) from rider_events where user_id = "
            "(select id from users where username = 'demo_pytest-flag')").fetchone(), (True, 1))
        # real users are not shown on the demo leaderboard
        names = {r["username"] for r in self.c.get("/leaderboards", headers=H(u)).json()}
        self.assertIn("pytest-flag", names)
        self.assertFalse(any(n.startswith("demo_") for n in names))
        dry = demo_reset.run(self.conn, dry_run=True)
        self.assertGreaterEqual(dry["rider_events"], 1)
        self.assertGreaterEqual(dry["points_ledger"], 1)
        with self.assertRaises(PermissionError):
            demo_reset.run(self.conn, allow_writes=False)
        done = demo_reset.run(self.conn, allow_writes=True)
        self.assertEqual(done, dry)
        after = demo_reset.run(self.conn, dry_run=True)
        self.assertEqual(sum(after.values()), 0)
        self.assertEqual(self.conn.execute(
            "select count(*) from pg_trigger where tgname = 'points_ledger_no_mutation' and tgenabled <> 'O'").fetchone()[0], 0)

    def test_spot_visit_writes_one_demo_event(self):
        row = self.conn.execute(
            "select s.id, l.stop_id from nearby_spots s join spot_stop_links l on l.spot_id = s.id "
            "where s.active and s.removed_at is null order by l.distance_m nulls last limit 1").fetchone()
        if not row:
            self.skipTest("no spot with a station in the database")
        spot_id, stop_id = str(row[0]), row[1]
        u = "pytest-spot"
        r = self.c.post(f"/spots/{spot_id}/visit", json={}, headers=H(u))
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual((r.json()["spot_id"], r.json()["already_visited_today"]), (spot_id, False))
        self.assertEqual(r.json()["stop_id"], stop_id)
        count = lambda: self.conn.execute(
            "select count(*), bool_and(is_synthetic) from rider_events where event_type='visit' "
            "and payload->>'spot_id' = %s and user_id = (select id from users where username = %s)",
            (spot_id, "demo_" + u)).fetchone()
        self.assertEqual(count(), (1, True))
        again = self.c.post(f"/spots/{spot_id}/visit", json={}, headers=H(u))
        self.assertEqual((again.status_code, again.json()["already_visited_today"]), (200, True))
        self.assertEqual(count(), (1, True))                  # no duplicate event
        self.assertEqual(self.c.post(f"/spots/{spot_id}/visit", json={"stop_id": "place-nowhere"}, headers=H(u)).status_code, 422)
        self.assertEqual(self.c.post("/spots/00000000-0000-4000-8000-000000000000/visit", headers=H(u)).status_code, 404)
        self.assertEqual(self.c.post("/spots/not-a-uuid/visit", headers=H(u)).status_code, 404)
        self.assertEqual(self.c.get("/me/points", headers=H(u)).json()["balance"], 0)          # no points
        self.assertEqual(self.c.get("/me/collection", headers=H(u)).json()["stops"], [])       # not a check-in

    def test_too_fast_with_database(self):
        """On by default with the database: two far stations in the same second are refused."""
        a = self.conn.execute("select id, lat, lon from stops where id='place-pktrm'").fetchone()
        b = self.conn.execute("select id, lat, lon from stops where id='place-ccmnl'").fetchone()
        mk = lambda s: {"stop_id": s[0], "lat": s[1], "lon": s[2], "client_time": "2026-11-21T12:00:00"}
        with patch.dict(os.environ, {"SPEED_CHECK": "strict"}):
            self.assertEqual(self.c.post("/checkins", json=mk(a), headers=H("pytest-fast")).status_code, 201)
            r = self.c.post("/checkins", json=mk(b), headers=H("pytest-fast"))
            self.assertEqual((r.status_code, r.json()["detail"]), (422, "too_fast"))
            self.assertEqual(self.store.last_checkin("pytest-fast")[1:], (a[1], a[2]))

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
