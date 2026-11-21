"""Deterministic ids: seed slugs map to uuid5 so memory and Postgres agree."""
from uuid import NAMESPACE_URL, UUID, uuid5

NAMESPACE = uuid5(NAMESPACE_URL, "https://t-quest/insights-sponsors")


def slug_to_uuid(slug: str) -> UUID:
    return uuid5(NAMESPACE, slug)
