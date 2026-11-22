"""Shared demo auth for every T-Quest service (stdlib only).

APP_ENV=dev (default): the bearer token may be a plain sandbox username (local demos and tests).
APP_ENV=prod: the bearer token must be a short-lived HMAC-signed token issued by the demo login endpoint,
signed with TOKEN_SECRET. No personal data: a token carries only a sandbox username and its times.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import time

USERNAME_RE = re.compile(r"^[A-Za-z0-9]{3,32}$")
MIN_SECRET_LEN = 16
DEFAULT_TTL_S = 3600


class AuthError(Exception):
    """Raised with a short, generic reason; callers answer 401 without detail."""


def app_env() -> str:
    return "prod" if os.environ.get("APP_ENV", "dev").strip().lower() == "prod" else "dev"


def token_secret() -> str | None:
    return os.environ.get("TOKEN_SECRET") or None


def require_prod_config() -> None:
    """Call at startup. In prod, fail closed when the signing secret is missing or too short."""
    if app_env() == "prod":
        s = token_secret()
        if not s or len(s) < MIN_SECRET_LEN:
            raise RuntimeError(f"APP_ENV=prod requires TOKEN_SECRET of at least {MIN_SECRET_LEN} characters")


def valid_username(name: str) -> bool:
    return bool(isinstance(name, str) and USERNAME_RE.match(name))


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(payload_b64: str, secret: str) -> str:
    return _b64(hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).digest())


def issue_token(username: str, secret: str, ttl_s: int = DEFAULT_TTL_S, now: float | None = None) -> str:
    if not valid_username(username):
        raise ValueError("username must be 3-32 letters or digits")
    if not secret or len(secret) < MIN_SECRET_LEN:
        raise ValueError("secret too short")
    t = int(now if now is not None else time.time())
    payload = _b64(json.dumps({"sub": username, "iat": t, "exp": t + int(ttl_s)}, separators=(",", ":")).encode())
    return f"{payload}.{_sign(payload, secret)}"


def verify_token(token: str, secret: str, now: float | None = None) -> str:
    """Return the username or raise AuthError."""
    try:
        payload_b64, sig = token.split(".", 1)
    except (ValueError, AttributeError):
        raise AuthError("malformed")
    if not secret or not hmac.compare_digest(_sign(payload_b64, secret), sig):
        raise AuthError("bad signature")
    try:
        data = json.loads(_unb64(payload_b64))
        sub, exp = data["sub"], int(data["exp"])
    except (ValueError, KeyError, TypeError):
        raise AuthError("malformed")
    if (now if now is not None else time.time()) >= exp:
        raise AuthError("expired")
    if not valid_username(sub):
        raise AuthError("malformed")
    return sub


def user_from_authorization(header: str | None) -> str:
    """Resolve the Authorization header to a username, or raise AuthError."""
    if not header or not header.lower().startswith("bearer "):
        raise AuthError("missing")
    token = header[7:].strip()
    if not token:
        raise AuthError("missing")
    if app_env() == "prod":
        secret = token_secret()
        if not secret:
            raise AuthError("server not configured")
        return verify_token(token, secret)
    if "." in token and token_secret():  # dev also accepts signed tokens
        try:
            return verify_token(token, token_secret())
        except AuthError:
            pass
    return token  # dev: the bearer token is the sandbox username
