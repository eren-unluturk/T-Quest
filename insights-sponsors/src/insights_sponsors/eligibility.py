from collections.abc import Collection

from .models import Offer


def is_eligible(offer: Offer, rank: int, badges: Collection[str]) -> bool:
    """True when the rank meets min_rank and any required badge is held.

    Pure function so game-engine's redemption logic can mirror it.
    """
    if rank < offer.min_rank:
        return False
    return offer.required_badge_id is None or offer.required_badge_id in badges
