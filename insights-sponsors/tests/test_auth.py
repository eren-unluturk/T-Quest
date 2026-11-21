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


def test_strict_mode_501(auth_client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "strict")
    assert auth_client.get("/whoami", headers=auth_headers).status_code == 501
