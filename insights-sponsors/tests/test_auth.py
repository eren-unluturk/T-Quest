import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from insights_sponsors.auth import current_user_id
from insights_sponsors.config import settings


@pytest.fixture
def auth_client() -> TestClient:
    app = FastAPI()

    @app.get("/whoami")
    def whoami(uid: str = Depends(current_user_id)):
        return {"user_id": uid}

    return TestClient(app)


def test_missing_header_401(auth_client):
    assert auth_client.get("/whoami").status_code == 401


def test_basic_scheme_401(auth_client):
    r = auth_client.get("/whoami", headers={"Authorization": "Basic x"})
    assert r.status_code == 401


def test_empty_token_401(auth_client):
    r = auth_client.get("/whoami", headers={"Authorization": "Bearer "})
    assert r.status_code == 401


def test_dev_mode_returns_user_id(auth_client, auth_headers):
    r = auth_client.get("/whoami", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == {"user_id": "user-1"}


def test_prod_requires_signed_tokens(auth_client, auth_headers, monkeypatch):
    import tquest_auth as A

    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("TOKEN_SECRET", "k" * 32)
    assert auth_client.get("/whoami", headers=auth_headers).status_code == 401  # plain username refused
    good = {"Authorization": "Bearer " + A.issue_token("riderOne", "k" * 32)}
    assert auth_client.get("/whoami", headers=good).json() == {"user_id": "riderOne"}
    expired = {"Authorization": "Bearer " + A.issue_token("riderOne", "k" * 32, ttl_s=1, now=1)}
    assert auth_client.get("/whoami", headers=expired).status_code == 401
    tampered = {"Authorization": good["Authorization"][:-3] + "AAA"}
    assert auth_client.get("/whoami", headers=tampered).status_code == 401
    wrong = {"Authorization": "Bearer " + A.issue_token("riderOne", "z" * 32)}
    assert auth_client.get("/whoami", headers=wrong).status_code == 401
    assert auth_client.get("/whoami").status_code == 401


def test_demo_login_issues_working_token(client, monkeypatch):
    import tquest_auth as A

    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("TOKEN_SECRET", "k" * 32)
    r = client.post("/auth/demo-login", json={"username": "riderTwo"})
    assert r.status_code == 200 and r.json()["username"] == "riderTwo" and r.json()["expires_in"] > 0
    assert A.verify_token(r.json()["token"], "k" * 32) == "riderTwo"
    assert client.get("/categories", headers={"Authorization": "Bearer " + r.json()["token"]}).status_code == 200
    for bad in ("ab", "has space", "a@b.com", "x" * 40, ""):
        assert client.post("/auth/demo-login", json={"username": bad}).status_code == 422


def test_login_unavailable_in_prod_without_secret(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("TOKEN_SECRET", raising=False)
    assert client.post("/auth/demo-login", json={"username": "riderTwo"}).status_code == 503
