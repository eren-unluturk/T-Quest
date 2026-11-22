import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import _shared  # noqa: F401
import tquest_auth

router = APIRouter()


class LoginRequest(BaseModel):
    username: str


class LoginResponse(BaseModel):
    token: str
    username: str
    expires_in: int


@router.post("/auth/demo-login", response_model=LoginResponse)
def demo_login(body: LoginRequest):
    """Sandbox login: any 3-32 letter/digit username, no password, no personal data. Issues a short-lived token.
    Without TOKEN_SECRET (dev only) the token is the username itself."""
    if not tquest_auth.valid_username(body.username):
        raise HTTPException(status_code=422, detail="username must be 3-32 letters or digits")
    ttl = int(os.environ.get("TOKEN_TTL_S", tquest_auth.DEFAULT_TTL_S))
    secret = tquest_auth.token_secret()
    if secret:
        token = tquest_auth.issue_token(body.username, secret, ttl_s=ttl)
    elif tquest_auth.app_env() == "dev":
        token = body.username
    else:
        raise HTTPException(status_code=503, detail="login unavailable")
    return LoginResponse(token=token, username=body.username, expires_in=ttl)
