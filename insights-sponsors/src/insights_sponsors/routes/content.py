import random
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import current_user_id
from ..models import ContentItem, Fact, Fave, FunFact, LoadingFact, StopFacts, TrailSite
from ..repo import Repository, get_repository

router = APIRouter()


@router.get("/stops/{stop_id}/facts", response_model=StopFacts)
def stop_facts(
    stop_id: str,
    _user: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
):
    facts = repo.stop_facts(stop_id)
    if facts is None:
        raise HTTPException(status_code=404, detail="unknown stop")
    if not facts.facts:
        # No history recorded: fall back to one general Boston fact, picked by stop id so it is stable.
        general = repo.loading_facts()
        note = "No history recorded yet for this stop."
        if general:
            g = general[sum(map(ord, stop_id)) % len(general)]
            fb = Fact(id=g.id, kind="fast_fact", title="About Boston and the T", body=g.body, source_url=g.source_url)
            return facts.model_copy(update={"facts": [fb], "fallback": True, "note": note})
        return facts.model_copy(update={"fallback": True, "note": note})
    return facts


@router.get("/freedom-trail", response_model=list[TrailSite])
def freedom_trail(
    _user: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
):
    return sorted(repo.trail_sites(), key=lambda t: t.order)


@router.get("/fun-facts", response_model=list[FunFact])
def fun_facts(
    repo: Annotated[Repository, Depends(get_repository)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    random_order: Annotated[bool, Query(alias="random")] = True,
):
    facts = repo.fun_facts()
    if random_order:
        facts = random.sample(facts, k=min(limit, len(facts)))
    return facts[:limit]


@router.get("/stops/{stop_id}/content", response_model=list[ContentItem])
def stop_content(
    stop_id: str,
    _user: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
    category: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """Open-source tourist content within about 500 m of the stop. Every item carries source_url,
    license and attribution; clients must display the attribution."""
    if repo.get_stop(stop_id) is None:
        raise HTTPException(status_code=404, detail="unknown stop")
    items = repo.stop_content(stop_id)
    if category:
        items = [i for i in items if i.category == category]
    return items[:limit]


@router.get("/loading-facts", response_model=list[LoadingFact])
def loading_facts(
    repo: Annotated[Repository, Depends(get_repository)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
):
    return repo.loading_facts()[:limit]
