from functools import lru_cache

from ..config import settings
from .base import Repository
from .memory import MemoryRepository


@lru_cache(maxsize=1)
def _memory_repo() -> MemoryRepository:
    return MemoryRepository()


@lru_cache(maxsize=1)
def _postgres_repo() -> Repository:
    from .postgres import PostgresRepository

    return PostgresRepository()


def get_repository() -> Repository:
    """FastAPI dependency: the process-wide repository."""
    if settings.data_backend == "memory":
        return _memory_repo()
    return _postgres_repo()


__all__ = ["Repository", "MemoryRepository", "get_repository"]
