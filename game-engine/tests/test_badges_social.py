import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from game_engine import badges
from game_engine.badges import Quest, completed_quests, quest_progress, unlocked_badges
from game_engine.points import LedgerEntry
from game_engine.social import FriendBook, FriendError, leaderboard, points_in_period

NOW = datetime(2026, 11, 21, 12, 0, 0)


class BadgeTests(unittest.TestCase):
    def test_line_complete(self):
        got = unlocked_badges(visited_stops=badges.LINES["Red"], rank=1, already_have=set())
        self.assertIn("line-red-complete", got)
        self.assertNotIn("line-green-b-complete", got)

    def test_partial_line_no_badge(self):
        stops = set(badges.LINES["Red"]) - {"harvard"}
        self.assertNotIn("line-red-complete", unlocked_badges(visited_stops=stops, rank=1, already_have=set()))

    def test_freedom_trail(self):
        got = unlocked_badges(visited_stops=badges.FREEDOM_TRAIL, rank=1, already_have=set())
        self.assertIn("freedom-trail", got)

    def test_rank_badges(self):
        self.assertEqual(unlocked_badges(visited_stops=set(), rank=2, already_have=set()), set())
        self.assertEqual(unlocked_badges(visited_stops=set(), rank=3, already_have=set()), {"rank-3"})
        self.assertEqual(unlocked_badges(visited_stops=set(), rank=5, already_have={"rank-3"}),
                         {"rank-4", "rank-5"})

    def test_no_repeat(self):
        got = unlocked_badges(visited_stops=badges.LINES["Red"], rank=1, already_have={"line-red-complete"})
        self.assertNotIn("line-red-complete", got)

    def test_physical_rewards(self):
        self.assertEqual(badges.physical_rewards_for({"line-red-complete", "nope"}), {"red-line-patch"})


class CatalogTests(unittest.TestCase):
    def test_catalog_needs_every_station_of_one_route(self):
        from game_engine.badges import Catalog
        cat = Catalog(lines={"line-x-complete": [frozenset({"a", "b"}), frozenset({"a", "c"})]},
                      trail=frozenset({"a", "b"}))
        got = unlocked_badges(visited_stops={"a", "c"}, rank=1, already_have=set(), catalog=cat)
        self.assertEqual(got, {"line-x-complete"})
        got = unlocked_badges(visited_stops={"b", "c"}, rank=1, already_have=set(), catalog=cat)
        self.assertEqual(got, set())
        got = unlocked_badges(visited_stops={"a", "b"}, rank=1, already_have=set(), catalog=cat)
        self.assertEqual(got, {"line-x-complete", "freedom-trail"})

    def test_empty_trail_is_off(self):
        from game_engine.badges import Catalog
        cat = Catalog(lines={}, trail=frozenset())
        self.assertEqual(unlocked_badges(visited_stops={"a"}, rank=1, already_have=set(), catalog=cat), set())


class QuestTests(unittest.TestCase):
    q = Quest("q1", "Coffee run", frozenset({"a", "b"}), 40, "coffee", "shop1")

    def test_progress(self):
        self.assertEqual(quest_progress(self.q, {"a", "z"}), (1, 2))

    def test_completed_once(self):
        self.assertEqual(completed_quests([self.q], {"a"}, set()), [])
        self.assertEqual(completed_quests([self.q], {"a", "b"}, set()), [self.q])
        self.assertEqual(completed_quests([self.q], {"a", "b"}, {"q1"}), [])

    def test_any_n_stops(self):
        q = Quest("q2", "Any three", frozenset({"a", "b", "c", "d"}), 40, "local-explorer", None, 3)
        self.assertEqual(quest_progress(q, {"a", "b"}), (2, 3))
        self.assertEqual(quest_progress(q, {"a", "b", "c", "d"}), (3, 3))
        self.assertEqual(completed_quests([q], {"a", "b"}, set()), [])
        self.assertEqual(completed_quests([q], {"a", "c", "d"}, set()), [q])
        self.assertEqual(completed_quests([q], {"a", "x", "y"}, set()), [])


class FriendTests(unittest.TestCase):
    def test_add_is_mutual(self):
        fb = FriendBook()
        fb.add("ann", "bob")
        self.assertEqual(fb.list("ann"), ["bob"])
        self.assertEqual(fb.list("bob"), ["ann"])

    def test_errors(self):
        fb = FriendBook()
        with self.assertRaises(FriendError) as c:
            fb.add("ann", "ann")
        self.assertEqual(c.exception.http_status, 422)
        fb.add("ann", "bob")
        with self.assertRaises(FriendError) as c:
            fb.add("bob", "ann")
        self.assertEqual(c.exception.http_status, 409)


class LeaderboardTests(unittest.TestCase):
    scores = {"ann": 100, "bob": 250, "cy": 100, "di": 10}

    def test_global_with_ties(self):
        rows = leaderboard(self.scores)
        self.assertEqual([r["username"] for r in rows], ["bob", "ann", "cy", "di"])
        self.assertEqual([r["position"] for r in rows], [1, 2, 2, 4])

    def test_friends_scope(self):
        rows = leaderboard(self.scores, scope="friends", me="ann", friends=["bob"])
        self.assertEqual([r["username"] for r in rows], ["bob", "ann"])

    def test_limit_and_bad_scope(self):
        self.assertEqual(len(leaderboard(self.scores, limit=2)), 2)
        with self.assertRaises(ValueError):
            leaderboard(self.scores, scope="line")

    def test_period(self):
        entries = [LedgerEntry(NOW - timedelta(days=1), 20, "a"),
                   LedgerEntry(NOW - timedelta(days=10), 30, "b"),
                   LedgerEntry(NOW - timedelta(days=40), 50, "c"),
                   LedgerEntry(NOW, -5, "spend")]
        self.assertEqual(points_in_period(entries, "week", NOW), 20)
        self.assertEqual(points_in_period(entries, "month", NOW), 50)
        self.assertEqual(points_in_period(entries, "all", NOW), 100)


if __name__ == "__main__":
    unittest.main()
