import dataclasses
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from game_engine.checkin import distance_m, validate_checkin
from game_engine.points import Ledger, checkin_points
from game_engine.ranks import rank_for
from game_engine.redemption import RedemptionBook, RedemptionError

NOW = datetime(2026, 11, 21, 12, 0, 0)
PARK = (42.3564, -71.0624)  # fake stop


def base(**over):
    args = dict(consent=True, user_lat=PARK[0], user_lon=PARK[1],
                stop_lat=PARK[0], stop_lon=PARK[1], now=NOW,
                last_vehicle_seen_at=NOW - timedelta(seconds=60), last_checkin_at=None)
    args.update(over)
    return validate_checkin(**args)


class CheckinTests(unittest.TestCase):
    def test_distance_known(self):
        self.assertAlmostEqual(distance_m(0, 0, 0, 0), 0)
        self.assertTrue(100 < distance_m(42.0, -71.0, 42.001, -71.0) < 120)

    def test_ok(self):
        self.assertTrue(base().ok)

    def test_no_consent(self):
        r = base(consent=False)
        self.assertEqual((r.reason, r.http_status), ("no_consent", 403))

    def test_too_far(self):
        r = base(user_lat=PARK[0] + 0.002)
        self.assertEqual((r.reason, r.http_status), ("too_far", 422))

    def test_no_vehicle(self):
        self.assertEqual(base(last_vehicle_seen_at=None).reason, "no_vehicle")
        self.assertEqual(base(last_vehicle_seen_at=NOW - timedelta(minutes=10)).reason, "no_vehicle")

    def test_cooldown(self):
        r = base(last_checkin_at=NOW - timedelta(minutes=10))
        self.assertEqual((r.reason, r.http_status), ("cooldown", 409))
        self.assertTrue(base(last_checkin_at=NOW - timedelta(minutes=31)).ok)


class PointsTests(unittest.TestCase):
    def test_first_and_repeat(self):
        self.assertEqual(checkin_points(first_visit=True, repeats_today_at_stop=0, checkin_points_today=0), 20)
        self.assertEqual(checkin_points(first_visit=False, repeats_today_at_stop=0, checkin_points_today=0), 2)
        self.assertEqual(checkin_points(first_visit=False, repeats_today_at_stop=1, checkin_points_today=0), 0)

    def test_daily_cap(self):
        self.assertEqual(checkin_points(first_visit=True, repeats_today_at_stop=0, checkin_points_today=90), 10)
        self.assertEqual(checkin_points(first_visit=True, repeats_today_at_stop=0, checkin_points_today=100), 0)

    def test_ledger_append_only(self):
        led = Ledger()
        led.add(NOW, 20, "first_visit")
        led.add(NOW, -5, "spend")
        self.assertEqual((led.balance, led.lifetime), (15, 20))
        with self.assertRaises(AttributeError):
            led.entries.append(None)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            led.entries[0].delta = 999


class RankTests(unittest.TestCase):
    def test_tiers(self):
        self.assertEqual(rank_for(0), (1, 3, 1000))
        self.assertEqual(rank_for(999), (1, 3, 1000))
        self.assertEqual(rank_for(1000), (2, 5, 4000))
        self.assertEqual(rank_for(30000), (5, 12, None))


class RedemptionTests(unittest.TestCase):
    def issue(self, book, **over):
        args = dict(user_id="u1", store_id="s1", offer_id="o1", user_rank=2, min_rank=2, now=NOW)
        args.update(over)
        return book.issue(**args)

    def test_flow_single_use(self):
        book = RedemptionBook()
        red = self.issue(book)
        self.assertEqual(len(red.code), 10)
        self.assertEqual(book.verify(code=red.code, store_id="s1", now=NOW).status, "claimed")
        with self.assertRaises(RedemptionError) as c:
            book.verify(code=red.code, store_id="s1", now=NOW)
        self.assertEqual(c.exception.http_status, 410)

    def test_rank_requirement(self):
        with self.assertRaises(RedemptionError) as c:
            self.issue(RedemptionBook(), user_rank=1)
        self.assertEqual(c.exception.http_status, 403)

    def test_weekly_store_limit(self):
        book = RedemptionBook()
        self.issue(book)
        with self.assertRaises(RedemptionError) as c:
            self.issue(book, now=NOW + timedelta(days=3))
        self.assertEqual(c.exception.reason, "weekly_store_limit")
        self.issue(book, now=NOW + timedelta(days=8))
        self.issue(book, store_id="s2")

    def test_stock(self):
        book = RedemptionBook(stock={"o1": 1})
        self.issue(book)
        with self.assertRaises(RedemptionError) as c:
            self.issue(book, user_id="u2")
        self.assertEqual(c.exception.reason, "out_of_stock")

    def test_expiry_and_wrong_store(self):
        book = RedemptionBook()
        red = self.issue(book)
        with self.assertRaises(RedemptionError) as c:
            book.verify(code=red.code, store_id="other", now=NOW)
        self.assertEqual(c.exception.http_status, 404)
        with self.assertRaises(RedemptionError) as c:
            book.verify(code=red.code, store_id="s1", now=NOW + timedelta(hours=25))
        self.assertEqual(c.exception.reason, "expired")


if __name__ == "__main__":
    unittest.main()
