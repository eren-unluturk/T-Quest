from fastapi import Header, HTTPException

from .config import settings


def current_user_id(authorization: str | None = Header(default=None)) -> str:
    """Resolve the caller from `Authorization: Bearer <token>`.

    dev mode: the token itself is the user id.
    strict mode: real session verification is not wired yet.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="missing bearer token")
    scheme, _, token = authorization.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="malformed bearer token")
    if settings.auth_mode == "strict":
        raise HTTPException(
            status_code=501, detail="session verification not wired yet"
        )
    return token
