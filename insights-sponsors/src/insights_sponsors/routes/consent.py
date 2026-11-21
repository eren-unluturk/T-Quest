from typing import Annotated, get_args

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..auth import current_user_id
from ..config import CURRENT_POLICY_VERSION
from ..models import Consent, ConsentRequest, ConsentScope
from ..repo import Repository, get_repository

router = APIRouter()

SCOPES: tuple[str, ...] = get_args(ConsentScope)


def _default(scope: ConsentScope) -> Consent:
    return Consent(scope=scope, granted=False, policy_version=CURRENT_POLICY_VERSION)


@router.get("/consent", response_model=list[Consent])
def list_consent(
    user_id: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
):
    stored = {c.scope: c for c in repo.get_consents(user_id)}
    return [stored.get(s) or _default(s) for s in SCOPES]


@router.post("/consent", response_model=Consent, status_code=201)
def grant_consent(
    body: ConsentRequest,
    user_id: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
):
    if body.policy_version != CURRENT_POLICY_VERSION:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "policy version mismatch",
                "current": CURRENT_POLICY_VERSION,
            },
        )
    return repo.set_consent(user_id, body.scope, True, body.policy_version)


@router.delete("/consent/{scope}", response_model=Consent)
def revoke_consent(
    scope: ConsentScope,
    user_id: Annotated[str, Depends(current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
):
    if scope == "place_visits":
        # revoking deletes the data, even when the call is a repeat
        repo.delete_place_visits(user_id)
    existing = next((c for c in repo.get_consents(user_id) if c.scope == scope), None)
    if existing is None:
        return _default(scope)
    if not existing.granted:
        return existing  # already revoked: idempotent
    return repo.set_consent(user_id, scope, False, existing.policy_version)
