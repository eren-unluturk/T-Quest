import pytest
from fastapi.testclient import TestClient

from insights_sponsors.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def auth_headers() -> dict:
    return {"Authorization": "Bearer user-1"}
