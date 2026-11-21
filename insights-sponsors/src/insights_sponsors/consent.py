"""Consent gate.

Every read of non-MBTA location or place-visit data must go through
has_consent/require_consent.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException

from .auth import current_user_id
from .models import ConsentScope
from .repo import Repository, get_repository


def has_consent(repo: Repository, user_id: str, scope: ConsentScope) -> bool:
    """True only while the user's consent for `scope` is currently granted."""
    return any(c.scope == scope and c.granted for c in repo.get_consents(user_id))


def require_consent(scope: ConsentScope) -> Callable[..., str]:
    """FastAPI dependency factory: 403 unless the caller granted `scope`.

    Returns the user id so routes can use it directly.
    """

    def dependency(
        user_id: Annotated[str, Depends(current_user_id)],
        repo: Annotated[Repository, Depends(get_repository)],
    ) -> str:
        if not has_consent(repo, user_id, scope):
            raise HTTPException(status_code=403, detail=f"consent required: {scope}")
        return user_id

    return dependency
