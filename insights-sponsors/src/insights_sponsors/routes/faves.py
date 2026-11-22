from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from ..auth import current_user_id
from ..models import Fave
from ..repo import Repository, get_repository

router = APIRouter()


@router.get("/me/faves", response_model=list[Fave])
def my_faves(
    user_id: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
):
    return repo.faves(user_id)


@router.post("/me/faves/{fact_id}", status_code=204)
def add_fave(
    fact_id: str,
    user_id: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
):
    if not repo.add_fave(user_id, fact_id):
        raise HTTPException(status_code=404, detail="unknown fact")
    return Response(status_code=204)


@router.delete("/me/faves/{fact_id}", status_code=204)
def remove_fave(
    fact_id: str,
    user_id: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
):
    repo.remove_fave(user_id, fact_id)
    return Response(status_code=204)
