from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

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
):
    found = repo.offers(stop_id=stop_id, store_id=store_id, category=category)
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
