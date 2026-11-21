"""Rank from lifetime points."""
from . import config


def rank_for(lifetime_points):
    """Return (rank, discount_pct, next_rank_at or None)."""
    current = config.RANKS[0]
    for tier in config.RANKS:
        if lifetime_points >= tier[1]:
            current = tier
    idx = config.RANKS.index(current)
    nxt = config.RANKS[idx + 1][1] if idx + 1 < len(config.RANKS) else None
    return current[0], current[2], nxt
