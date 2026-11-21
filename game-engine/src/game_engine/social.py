"""Friends and leaderboard rules. In-memory; no database."""
from datetime import datetime, timedelta


class FriendError(Exception):
    def __init__(self, reason, http_status):
        super().__init__(reason)
        self.reason = reason
        self.http_status = http_status


class FriendBook:
    """Mutual friendships between usernames."""

    def __init__(self):
        self._friends = {}

    def add(self, user, other):
        if user == other:
            raise FriendError("cannot_friend_self", 422)
        if other in self._friends.get(user, set()):
            raise FriendError("already_friends", 409)
        self._friends.setdefault(user, set()).add(other)
        self._friends.setdefault(other, set()).add(user)

    def list(self, user):
        return sorted(self._friends.get(user, set()))


def points_in_period(ledger_entries, period, now):
    """Sum positive points in the period. period: week | month | all."""
    if period == "all":
        cutoff = None
    elif period == "week":
        cutoff = now - timedelta(days=7)
    elif period == "month":
        cutoff = now - timedelta(days=30)
    else:
        raise ValueError("period must be week, month or all")
    return sum(e.delta for e in ledger_entries
               if e.delta > 0 and (cutoff is None or e.at > cutoff))


def leaderboard(scores, *, scope="global", me=None, friends=(), limit=50):
    """scores: dict username -> points.

    scope global = everyone; friends = me plus my friends.
    Ties share a position (1, 2, 2, 4).
    """
    if scope == "friends":
        allowed = set(friends) | ({me} if me else set())
        scores = {u: p for u, p in scores.items() if u in allowed}
    elif scope != "global":
        raise ValueError("scope must be global or friends")
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    rows = []
    last_points = None
    last_pos = 0
    for i, (user, pts) in enumerate(ordered, start=1):
        pos = last_pos if pts == last_points else i
        rows.append({"position": pos, "username": user, "points": pts})
        last_points, last_pos = pts, pos
    return rows[:limit]
