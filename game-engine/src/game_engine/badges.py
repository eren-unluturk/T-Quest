"""Badge unlock rules and sponsored quests. Pure functions; no database.

The line, trail and quest data below is FAKE placeholder data. Replace it with
the real catalog from insights-sponsors (issue #7) when it arrives.
"""
from dataclasses import dataclass
from typing import Optional

# line id -> set of stop ids on that line (fake)
LINES = {
    "green-b": {"park", "boylston", "arlington", "copley"},
    "red": {"alewife", "harvard", "park", "downtown", "south-station"},
}

# Freedom Trail stops (fake)
FREEDOM_TRAIL = {"park", "downtown", "state", "haymarket"}

# rank number -> badge id
RANK_BADGES = {3: "rank-3-patch", 5: "rank-5-patch"}

# badge id -> physical reward it unlocks (fake)
PHYSICAL_REWARDS = {
    "line-red": "red-line-patch",
    "freedom-trail": "freedom-trail-sticker",
    "rank-3-patch": "rank-3-patch",
}


def line_badge_id(line_id):
    return "line-" + line_id


def unlocked_badges(*, visited_stops, rank, already_have):
    """Return the set of badge ids newly earned. Never repeats a badge."""
    visited = set(visited_stops)
    earned = set()
    for line_id, stops in LINES.items():
        if stops <= visited:
            earned.add(line_badge_id(line_id))
    if FREEDOM_TRAIL <= visited:
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


def quest_progress(quest, visited_stops):
    """Return (done, total) for a visit-these-stops quest."""
    done = len(quest.goal_stops & set(visited_stops))
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
