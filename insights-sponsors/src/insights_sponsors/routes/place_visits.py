from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from ..auth import current_user_id
from ..consent import require_consent
from ..models import PlaceVisit, PlaceVisitAck, PlaceVisitIn, PlaceVisitsDeleted
from ..repo import Repository, get_repository
from ..repo.memory import PLACE_VISIT_RETENTION_DAYS

router = APIRouter()

COORDINATE_DECIMALS = 3  # about 100 m
MAX_AGE = timedelta(days=7)
MAX_FUTURE = timedelta(minutes=5)


@router.post("/place-visits", response_model=PlaceVisitAck, status_code=201)
def add_place_visit(
    body: PlaceVisitIn,
    user_id: Annotated[str, Depends(require_consent("place_visits"))],
    repo: Annotated[Repository, Depends(get_repository)],
):
    visited_at = body.visited_at
    if visited_at.tzinfo is None:  # treat a bare timestamp as UTC
        visited_at = visited_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if visited_at < now - MAX_AGE:
        raise HTTPException(status_code=422, detail="visited_at is more than 7 days old")
    if visited_at > now + MAX_FUTURE:
        raise HTTPException(status_code=422, detail="visited_at is in the future")

    repo.add_place_visit(
        user_id,
        PlaceVisit(
            time=visited_at,
            user_id=user_id,
            lat=round(body.lat, COORDINATE_DECIMALS),
            lon=round(body.lon, COORDINATE_DECIMALS),
            place_category=body.place_category,
            store_id=body.store_id,
        ),
    )
    return PlaceVisitAck(accepted=True, retained_days=PLACE_VISIT_RETENTION_DAYS)


@router.delete("/place-visits", response_model=PlaceVisitsDeleted)
def delete_place_visits(
    user_id: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
):
    """Always allowed, with or without consent, so users can erase their data."""
    return PlaceVisitsDeleted(deleted=repo.delete_place_visits(user_id))
