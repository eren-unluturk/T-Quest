from functools import lru_cache

from ..config import settings
from .base import Repository
from .memory import MemoryRepository


@lru_cache(maxsize=1)
def _memory_repo() -> MemoryRepository:
    return MemoryRepository()


def get_repository() -> Repository:
    """FastAPI dependency: the process-wide repository."""
    if settings.data_backend == "memory":
        return _memory_repo()
    raise NotImplementedError("postgres backend is not implemented yet")


__all__ = ["Repository", "MemoryRepository", "get_repository"]
