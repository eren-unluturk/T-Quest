from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import current_user_id
from ..repo import Repository, get_repository
from ..spots import (
    CategoryRef,
    NearbyResponse,
    Spot,
    build_facets,
    filter_spots,
    public_labels,
    sort_spots,
)

router = APIRouter()


@router.get("/stops/{stop_id}/nearby", response_model=NearbyResponse)
def nearby(
    stop_id: str,
    _user: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
    category: Annotated[list[str] | None, Query()] = None,
    label: Annotated[list[str] | None, Query()] = None,
    match: Literal["any", "all"] = "all",
    sponsored: bool | None = None,
    include_demo: bool = True,
    q: str | None = None,
    sort: Literal["distance", "name", "sponsored_first"] = "distance",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    if repo.get_stop(stop_id) is None:
        raise HTTPException(status_code=404, detail="unknown stop")
    base = [public_labels(s) for s in repo.spots_for_stop(stop_id)]
    base = filter_spots(base, include_demo=include_demo)
    facets = build_facets(base)  # chips for the whole stop, before category/label filters
    found = filter_spots(
        base, categories=category, labels=label, match=match, sponsored=sponsored, q=q
    )
    found = sort_spots(found, sort)
    return NearbyResponse(
        stop_id=stop_id,
        total=len(found),
        limit=limit,
        offset=offset,
        spots=found[offset : offset + limit],
        facets=facets,
    )


@router.get("/categories", response_model=list[CategoryRef])
def categories(
    _user: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
):
    return repo.spot_categories()


@router.get("/labels")
def labels(
    _user: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
):
    return repo.label_types()


@router.get("/spots/{spot_id}", response_model=Spot)
def spot(
    spot_id: str,
    _user: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
):
    found = repo.get_spot(spot_id)
    if found is None:
        raise HTTPException(status_code=404, detail="unknown spot")
    return public_labels(found)
