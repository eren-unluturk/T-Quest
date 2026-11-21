import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from game_engine.delay import compensation_points, home_line

NOW = datetime(2026, 11, 21, 12, 0, 0)


def rides(line, n, days_ago=1):
    return [(NOW - timedelta(days=days_ago, minutes=i), line) for i in range(n)]


class HomeLineTests(unittest.TestCase):
    def test_most_ridden(self):
        self.assertEqual(home_line(rides("green", 8) + rides("red", 6), NOW), "green")

    def test_too_few_rides(self):
        self.assertIsNone(home_line(rides("green", 4), NOW))

    def test_old_rides_ignored(self):
        self.assertIsNone(home_line(rides("green", 10, days_ago=45), NOW))
        self.assertIsNone(home_line([], NOW))

    def test_tie_goes_to_most_recent(self):
        data = rides("green", 5, days_ago=10) + rides("red", 5, days_ago=1)
        self.assertEqual(home_line(data, NOW), "red")


class CompensationTests(unittest.TestCase):
    def pay(self, **over):
        args = dict(alert_id="a1", alert_line="green", alert_effect="outage",
                    user_home_line="green", already_paid_alerts=set())
        args.update(over)
        return compensation_points(**args)

    def test_paid(self):
        self.assertEqual(self.pay(), 50)

    def test_not_home_line(self):
        self.assertEqual(self.pay(user_home_line="red"), 0)
        self.assertEqual(self.pay(user_home_line=None), 0)

    def test_minor_delay_not_paid(self):
        self.assertEqual(self.pay(alert_effect="delay"), 0)

    def test_once_per_alert(self):
        self.assertEqual(self.pay(already_paid_alerts={"a1"}), 0)


if __name__ == "__main__":
    unittest.main()
