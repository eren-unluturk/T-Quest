"""Rank from lifetime points."""
from . import config


def _tier_index(lifetime_points):
    idx = 0
    for i, tier in enumerate(config.RANKS):
        if lifetime_points >= tier[1]:
            idx = i
    return idx


def rank_for(lifetime_points):
    """Return (rank, discount_pct, next_rank_at or None)."""
    idx = _tier_index(lifetime_points)
    tier = config.RANKS[idx]
    nxt = config.RANKS[idx + 1][1] if idx + 1 < len(config.RANKS) else None
    return tier[0], tier[2], nxt


def rank_info(lifetime_points):
    """Full rank details for GET /me/rank (name, avatar, next rank)."""
    idx = _tier_index(lifetime_points)
    tier = config.RANKS[idx]
    nxt = config.RANKS[idx + 1] if idx + 1 < len(config.RANKS) else None
    return {
        "rank": tier[0],
        "name": tier[3],
        "avatar_key": tier[4],
        "discount_pct": tier[2],
        "lifetime_points": lifetime_points,
        "next_rank": nxt[0] if nxt else None,
        "next_rank_name": nxt[3] if nxt else None,
        "next_rank_at": nxt[1] if nxt else None,
        "points_to_next": (nxt[1] - lifetime_points) if nxt else None,
    }