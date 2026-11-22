"""Storage for the game-engine service.

MemoryStore keeps everything in Python dicts (demo and unit tests).
PgStore (pg_store.py) keeps it in the shared Tiger Data database.
Both offer the same methods, so app.py does not care which one it has.

User argument is always the USERNAME (the demo bearer token).
Ledger reasons are encoded as "reason" or "reason:ref_id" (e.g. "quest:q1").
"""
from datetime import timedelta

from . import badges
from .points import Ledger
from .redemption import RedemptionBook, RedemptionError

# FAKE demo reference data (used by MemoryStore only)
DEMO_STOPS = {
    "park": {"lat": 42.3564, "lon": -71.0624, "mode": "subway"},
    "harvard": {"lat": 42.3736, "lon": -71.1190, "mode": "subway"},
    "alewife": {"lat": 42.3954, "lon": -71.1425, "mode": "subway"},
    "downtown": {"lat": 42.3555, "lon": -71.0602, "mode": "subway"},
    "south-station": {"lat": 42.3519, "lon": -71.0552, "mode": "subway"},
    # Real MBTA station ids the web app sends (coordinates from the stops table), so check-in works in memory mode.
    "place-pktrm": {"lat": 42.3564, "lon": -71.0624, "mode": "subway"},
    "place-harsq": {"lat": 42.373362, "lon": -71.118956, "mode": "subway"},
    "place-davis": {"lat": 42.39674, "lon": -71.121815, "mode": "subway"},
    "place-fenwy": {"lat": 42.345403, "lon": -71.104213, "mode": "subway"},
    "place-kencl": {"lat": 42.348949, "lon": -71.095169, "mode": "subway"},
}
DEMO_OFFERS = {
    "o1": {"store_id": "s1", "title": "5% off a coffee", "min_rank": 1},
    "o2": {"store_id": "s2", "title": "Free cookie", "min_rank": 5},
    # needs a badge and allows 2 per rider, to show those rules
    "o3": {"store_id": "s3", "title": "Red Line riders perk", "min_rank": 1,
           "required_badge_id": "line-red-complete", "per_user_limit": 2},
}
DEMO_QUESTS = [
    badges.Quest("q1", "Downtown loop", frozenset({"park", "downtown"}), 40, None, "sponsor1"),
]
# spot id -> {station id: distance in metres}. Placeholder spots; no real business is implied.
DEMO_SPOTS = {
    "demo-cafe": {"name": "Sample Cafe (demo)", "stops": {"park": 60.0}},
    "demo-bar": {"name": "Sample Bar (demo)", "stops": {"downtown": 90.0, "park": 280.0}},
}


def encode_reason(reason, ref_id=None):
    return f"{reason}:{ref_id}" if ref_id else reason


class MemoryStore:
    name = "memory"
    can_write = True

    def __init__(self):
        self.reset()

    def reset(self):
        self._ledgers = {}
        self._visits = {}      # user -> {stop_id: [datetime]}
        self._badges = {}
        self._friends = {}
        self._last = {}          # user -> (at, lat, lon) of the latest check-in
        self._spot_visits = []   # (user, spot_id, stop_id, at)
        self._book = RedemptionBook()
        self._redeemed = {}      # (user, offer_id) -> codes issued

    # reference data
    def stop(self, stop_id):
        return DEMO_STOPS.get(stop_id)

    def vehicle_seen_at(self, stop_id, now, lat=None, lon=None):
        return now  # demo: a vehicle is always nearby

    def quests(self):
        return list(DEMO_QUESTS)

    def physical_rewards_for(self, badge_ids):
        return sorted(badges.physical_rewards_for(badge_ids))

    def catalog(self):
        return badges.DEFAULT_CATALOG

    def offer(self, offer_id):
        return DEMO_OFFERS.get(offer_id)

    # users
    def ensure_user(self, user):
        self._ledgers.setdefault(user, Ledger())

    # check-ins
    def checkins_at_stop(self, user, stop_id):
        return list(self._visits.get(user, {}).get(stop_id, []))

    def visited_stops(self, user):
        return {s for s, v in self._visits.get(user, {}).items() if v}

    def record_checkin(self, user, stop_id, lat, lon, client_time, at, points, mode=None):
        self._visits.setdefault(user, {}).setdefault(stop_id, []).append(at)
        self._last[user] = (at, lat, lon)

    def last_checkin(self, user):
        """(at, lat, lon) of the user's latest check-in anywhere, or None."""
        return self._last.get(user)

    # spots (placeholder places near stops)
    def spot_stops(self, spot_id):
        """{station id: distance_m} for a spot, or None if the spot does not exist."""
        spot = DEMO_SPOTS.get(spot_id)
        return dict(spot["stops"]) if spot else None

    def spot_visited_since(self, user, spot_id, since):
        return any(u == user and s == spot_id and at >= since for u, s, _stop, at in self._spot_visits)

    def record_spot_visit(self, user, spot_id, stop_id, at):
        self._spot_visits.append((user, spot_id, stop_id, at))

    # points
    def ledger_entries(self, user):
        return self._ledgers.setdefault(user, Ledger()).entries

    def add_points(self, user, at, delta, reason, ref_type=None, ref_id=None):
        self._ledgers.setdefault(user, Ledger()).add(at, delta, encode_reason(reason, ref_id))

    def all_ledgers(self):
        return {u: l.entries for u, l in self._ledgers.items()}

    # badges
    def badges(self, user):
        return set(self._badges.get(user, set()))

    def add_badge(self, user, badge_id, at, source):
        self._badges.setdefault(user, set()).add(badge_id)

    # friends
    def add_friend(self, user, other):
        if user == other:
            return "self"
        if other in self._friends.get(user, set()):
            return "exists"
        self._friends.setdefault(user, set()).add(other)
        self._friends.setdefault(other, set()).add(user)
        return "ok"

    def friends(self, user):
        return sorted(self._friends.get(user, set()))

    # redemptions
    def issue_redemption(self, *, user, offer_id, offer, user_rank, balance, now):
        if user_rank < offer["min_rank"]:
            raise RedemptionError("rank_too_low", 403)
        need = offer.get("required_badge_id")
        if need and need not in self._badges.get(user, set()):
            raise RedemptionError("badge_required", 403)
        limit = offer.get("per_user_limit")
        if limit and self._redeemed.get((user, offer_id), 0) >= limit:
            raise RedemptionError("per_user_limit", 409)
        red = self._book.issue(user_id=user, store_id=offer["store_id"], offer_id=offer_id,
                               user_rank=user_rank, min_rank=offer["min_rank"], now=now)
        self._redeemed[(user, offer_id)] = self._redeemed.get((user, offer_id), 0) + 1
        return {"code": red.code, "offer_id": offer_id, "status": red.status,
                "expires_at": red.expires_at, "points_spent": 0}

    def verify_redemption(self, *, code, store_id, store_key, now):
        red = self._book.verify(code=code, store_id=store_id, now=now)
        return {"code": red.code, "offer_id": red.offer_id, "status": red.status,
                "expires_at": red.expires_at}
