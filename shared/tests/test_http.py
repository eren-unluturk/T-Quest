import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tquest_http as H  # noqa: E402


def make(monkeypatch, env=None):
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    app = FastAPI()

    @app.get("/x")
    def x():
        return {"ok": True}

    @app.post("/auth/demo-login")
    def login():
        return {"ok": True}

    @app.post("/w")
    def w():
        return {"ok": True}

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internals")

    H.harden(app)
    return TestClient(app, raise_server_exceptions=False)


def test_security_headers_and_generic_500(monkeypatch):
    c = make(monkeypatch)
    r = c.get("/x")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    b = c.get("/boom")
    assert b.status_code == 500 and b.json() == {"detail": "internal error"} and "secret" not in b.text


def test_body_limit(monkeypatch):
    c = make(monkeypatch, {"MAX_BODY_BYTES": "100"})
    assert c.post("/w", content=b"x" * 500).status_code == 413
    assert c.post("/w", content=b"x" * 10).status_code == 200


def test_login_rate_limit(monkeypatch):
    c = make(monkeypatch, {"RATE_LOGIN_PER_MIN": "3"})
    codes = [c.post("/auth/demo-login").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]


def test_write_rate_limit_per_token(monkeypatch):
    c = make(monkeypatch, {"RATE_WRITE_PER_MIN": "2"})
    h = {"Authorization": "Bearer abc"}
    assert [c.post("/w", headers=h).status_code for _ in range(3)] == [200, 200, 429]


def test_prod_cors_must_be_exact(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("TOKEN_SECRET", "s" * 32)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    with pytest.raises(RuntimeError):
        make(monkeypatch)
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(RuntimeError):
        make(monkeypatch)
    c = make(monkeypatch, {"CORS_ORIGINS": "https://app.example.test"})
    ok = c.get("/x", headers={"Origin": "https://app.example.test"})
    bad = c.get("/x", headers={"Origin": "https://evil.example.test"})
    assert ok.headers.get("access-control-allow-origin") == "https://app.example.test"
    assert "access-control-allow-origin" not in bad.headers


def test_limiter_window():
    t = [0.0]
    rl = H.RateLimiter(2, 10, clock=lambda: t[0])
    assert rl.allow("a") and rl.allow("a") and not rl.allow("a")
    t[0] = 11
    assert rl.allow("a")
