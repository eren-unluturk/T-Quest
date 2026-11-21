from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from pydantic import BaseModel

from ..auth import current_user_id
from ..eligibility import is_eligible
from ..models import Category, LocalPick, Offer, PhysicalReward
from ..repo import Repository, get_repository

router = APIRouter()


def is_active(offer: Offer, now: datetime) -> bool:
    return offer.starts_at <= now and (offer.ends_at is None or offer.ends_at > now)


@router.get("/stops/{stop_id}/local-picks", response_model=list[LocalPick])
def local_picks(
    stop_id: str,
    _user: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
):
    if repo.get_stop(stop_id) is None:
        raise HTTPException(status_code=404, detail="unknown stop")
    now = datetime.now(timezone.utc)
    picks: list[LocalPick] = []
    # Ask for every store so stores without active offers can be skipped
    # before the limit applies.
    for store, distance in repo.stores_near_stop(stop_id, 10_000):
        offers = [
            o
            for o in repo.offers(store_id=store.id)
            if o.placement == "local_pick" and is_active(o, now)
        ]
        if offers:
            picks.append(LocalPick(store=store, offers=offers, distance_m=distance))
        if len(picks) >= limit:
            break
    return picks


@router.get("/offers", response_model=list[Offer])
def offers(
    user_id: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
    stop_id: str | None = None,
    store_id: str | None = None,
    category: Category | None = None,
    eligible_only: bool = False,
    rank: Annotated[int | None, Query(ge=1, le=5)] = None,
    placement: Literal["local_pick", "sponsored_quest"] | None = None,
):
    found = repo.offers(stop_id=stop_id, store_id=store_id, category=category)
    if rank is not None:
        found = [o for o in found if o.min_rank <= rank]
    if placement is not None:
        found = [o for o in found if o.placement == placement]
    if eligible_only:
        rank = repo.user_rank(user_id)
        badges = repo.user_badges(user_id)
        found = [o for o in found if is_eligible(o, rank, badges)]
    return found


@router.get("/physical-rewards/catalog", response_model=list[PhysicalReward])
def physical_rewards_catalog(
    _user: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
):
    return repo.physical_rewards()


# Placeholder tiers mirror game-engine's rank table (3/5/7/10/12). The top tier unlocks a free item.
RANK_DISCOUNTS = {1: 3, 2: 5, 3: 7, 4: 10, 5: 12}
TOP_RANK = 5


class RankTier(BaseModel):
    rank: int
    discount_pct: int
    free_item: bool
    demo: bool = True
    offers: list[Offer]


@router.get("/rank-tiers", response_model=list[RankTier])
def rank_tiers(
    _user: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
):
    all_offers = repo.offers()
    return [
        RankTier(
            rank=r,
            discount_pct=pct,
            free_item=r == TOP_RANK,
            offers=[o for o in all_offers if o.min_rank == r],
        )
        for r, pct in RANK_DISCOUNTS.items()
    ]
