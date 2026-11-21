from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from ..analytics import boston_analytics, compute_analytics
from ..auth import current_user_id
from ..models import BostonAnalytics, MyAnalytics, Recommendations
from ..recommend import recommend
from ..repo import Repository, get_repository

router = APIRouter()


@router.get("/analytics/me", response_model=MyAnalytics)
def analytics_me(
    user_id: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
    period: Literal["week", "month", "all"] = "month",
):
    return compute_analytics(repo, user_id, period)


@router.get("/analytics/boston", response_model=BostonAnalytics)
def analytics_boston(
    _user: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
    period: Literal["week", "month"] = "week",
):
    return boston_analytics(repo, period)


@router.get("/recommendations", response_model=Recommendations)
def recommendations(
    user_id: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
    kind: Literal["route", "neighborhood", "stop"] | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
):
    return recommend(repo, user_id, kind=kind, limit=limit)
