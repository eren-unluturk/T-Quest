import pytest
from fastapi.testclient import TestClient

from insights_sponsors.main import create_app
from insights_sponsors.repo import get_repository
from insights_sponsors.repo.memory import MemoryRepository


@pytest.fixture
def repo() -> MemoryRepository:
    """A fresh in-memory repository per test."""
    return MemoryRepository()


@pytest.fixture
def client(repo: MemoryRepository) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repo
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict:
    return {"Authorization": "Bearer user-1"}
