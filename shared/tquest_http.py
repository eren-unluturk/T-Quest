"""Shared hardening for every T-Quest FastAPI service: CORS, security headers, body-size limit,
rate limits, generic errors. Config comes from env only.

  CORS_ORIGINS   comma-separated exact origins. Dev default "*". In prod a wildcard or empty value fails closed.
  MAX_BODY_BYTES request body limit (default 65536).
  RATE_WRITE_PER_MIN  per-IP and per-token limit on POST/PUT/PATCH/DELETE (default 60).
  RATE_LOGIN_PER_MIN  per-IP limit on /auth/ write routes (default 10).
  TRUST_PROXY=1  read the client IP from X-Forwarded-For (only behind a proxy you control).
"""
import os
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import tquest_auth

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect")


class RateLimiter:
    """In-memory sliding window per key. One process only (fine for a demo host)."""

    def __init__(self, limit: int, window_s: float = 60.0, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window_s, clock
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self.clock()
        q = self.hits[key]
        while q and now - q[0] >= self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        if len(self.hits) > 10000:  # bound memory
            for k in [k for k, v in self.hits.items() if not v][:5000]:
                self.hits.pop(k, None)
        return True


def cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "*" if tquest_auth.app_env() == "dev" else "")
    origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    if tquest_auth.app_env() == "prod" and (not origins or "*" in origins):
        raise RuntimeError("APP_ENV=prod requires CORS_ORIGINS set to the exact front-end origin(s), no wildcard")
    return origins or ["*"]


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd and os.environ.get("TRUST_PROXY", "") == "1":
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def harden(app: FastAPI, *, allow_methods=("GET", "POST", "DELETE", "OPTIONS"), extra_headers=()) -> None:
    tquest_auth.require_prod_config()
    origins = cors_origins()
    max_body = int(os.environ.get("MAX_BODY_BYTES", "65536"))
    write_limit = int(os.environ.get("RATE_WRITE_PER_MIN", "60"))
    write_ip, write_tok = RateLimiter(write_limit), RateLimiter(write_limit)
    login_ip = RateLimiter(int(os.environ.get("RATE_LOGIN_PER_MIN", "10")))

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.method != "OPTIONS":
            try:
                if int(request.headers.get("content-length") or 0) > max_body:
                    return JSONResponse({"detail": "request too large"}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "bad request"}, status_code=400)
            ip = _client_ip(request)
            if request.url.path.startswith("/auth/") and request.method in WRITE_METHODS and not login_ip.allow(ip):
                return JSONResponse({"detail": "too many requests"}, status_code=429, headers={"Retry-After": "60"})
            if request.method in WRITE_METHODS:
                tok = (request.headers.get("authorization") or "")[:200]
                if not write_ip.allow(ip) or (tok and not write_tok.allow(tok)):
                    return JSONResponse({"detail": "too many requests"}, status_code=429, headers={"Retry-After": "60"})
        try:
            response = await call_next(request)
        except Exception:  # never leak a stack trace
            response = JSONResponse({"detail": "internal error"}, status_code=500)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        if request.url.path not in DOCS_PATHS:
            response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        return response

    # added last so CORS headers are also present on the guard's early 413/429 answers
    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_methods=list(allow_methods),
        allow_headers=["Authorization", "Content-Type", *extra_headers], allow_credentials=False,
    )
