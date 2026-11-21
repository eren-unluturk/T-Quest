"""Badge unlock rules and sponsored quests. Pure functions; no database.

LINES and FREEDOM_TRAIL below are FAKE demo data (used by the in-memory store).
PgStore builds a real Catalog from the database instead.
"""
from dataclasses import dataclass
from typing import Optional

# line id -> set of stop ids on that line (fake)
LINES = {
    "Green-B": {"park", "boylston", "arlington", "copley"},
    "Red": {"alewife", "harvard", "park", "downtown", "south-station"},
}

# Freedom Trail stops (fake)
FREEDOM_TRAIL = {"park", "downtown", "state", "haymarket"}

# rank number -> badge id
RANK_BADGES = {3: "rank-3", 4: "rank-4", 5: "rank-5"}

# badge id -> physical reward it unlocks (fake)
PHYSICAL_REWARDS = {
    "line-red-complete": "red-line-patch",
    "freedom-trail": "freedom-trail-sticker",
    "rank-3": "rank-3-patch",
    "rank-4": "rank-4-patch",
}


def line_badge_id(line_id):
    return "line-%s-complete" % line_id.lower()


@dataclass(frozen=True)
class Catalog:
    """Where badges come from.

    lines: badge id -> list of station sets. A line badge is earned when ALL
    stations of at least one set are visited (one set per route, so a Green
    Line rider needs every station of one branch).
    trail: stations of the Freedom Trail. Empty means the badge is switched off.
    """
    lines: dict
    trail: frozenset


# Fake catalog for the in-memory demo and unit tests
DEFAULT_CATALOG = Catalog(
    lines={line_badge_id(k): [frozenset(v)] for k, v in LINES.items()},
    trail=frozenset(FREEDOM_TRAIL),
)


def unlocked_badges(*, visited_stops, rank, already_have, catalog=None):
    """Return the set of badge ids newly earned. Never repeats a badge."""
    catalog = catalog or DEFAULT_CATALOG
    visited = set(visited_stops)
    earned = set()
    for badge_id, station_sets in catalog.lines.items():
        if any(s and s <= visited for s in station_sets):
            earned.add(badge_id)
    if catalog.trail and catalog.trail <= visited:
        earned.add("freedom-trail")
    for min_rank, badge in RANK_BADGES.items():
        if rank >= min_rank:
            earned.add(badge)
    return earned - set(already_have)

def physical_rewards_for(badge_ids):
    return {PHYSICAL_REWARDS[b] for b in badge_ids if b in PHYSICAL_REWARDS}


@dataclass(frozen=True)
class Quest:
    id: str
    title: str
    goal_stops: frozenset
    reward_points: int
    reward_badge_id: Optional[str] = None
    sponsor_id: Optional[str] = None
    min_stops: Optional[int] = None  # None: every goal stop; N: any N distinct goal stops


def quest_progress(quest, visited_stops):
    """Return (done, total) for a visit-these-stops quest."""
    done = len(quest.goal_stops & set(visited_stops))
    if quest.min_stops:
        return min(done, quest.min_stops), quest.min_stops
    return done, len(quest.goal_stops)


def completed_quests(quests, visited_stops, already_done):
    """Quests finished now that were not finished before."""
    out = []
    for q in quests:
        if q.id in already_done:
            continue
        done, total = quest_progress(q, visited_stops)
        if total and done == total:
            out.append(q)
    return out
