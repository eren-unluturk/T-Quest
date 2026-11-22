from fastapi import Header, HTTPException

from . import _shared  # noqa: F401  (puts shared/ on sys.path)
import tquest_auth


def current_user_id(authorization: str | None = Header(default=None)) -> str:
    """Resolve the caller from `Authorization: Bearer <token>` via the shared auth module.

    APP_ENV=dev: the token may be a plain sandbox username. APP_ENV=prod: a signed, expiring token only.
    """
    try:
        return tquest_auth.user_from_authorization(authorization)
    except tquest_auth.AuthError:
        raise HTTPException(status_code=401, detail="invalid or missing credentials")
