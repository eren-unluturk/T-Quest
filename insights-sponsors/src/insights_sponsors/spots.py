"""Nearby spots: models and the single filter/sort implementation.

Label policy (hard rule): only `declared` or `certified` labels are ever returned or matched.
A `pending` label is invisible: it is dropped here even if a repository hands it over, and it
never counts toward a label filter. Labels are never inferred from names, photos or reviews.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .models import Offer

PUBLIC_STATUSES = ("declared", "certified")
LabelStatus = Literal["declared", "certified", "pending"]


class CategoryRef(BaseModel):
    slug: str
    display_name: str


class SpotLabel(BaseModel):
    slug: str
    display_name: str
    status: LabelStatus
    evidence_url: str | None = None
    declaration_note: str | None = None
    verified_at: datetime | None = None
    verified_by: str | None = None


class Spot(BaseModel):
    id: str
    name: str
    category: CategoryRef
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    placement_type: Literal["sponsored", "listed"]
    demo: bool
    sponsor_id: str | None = None
    distance_m: float | None = None
    source: str = "manual"
    labels: list[SpotLabel]
    offers: list[Offer]


class FacetCount(BaseModel):
    slug: str
    display_name: str
    count: int


class Facets(BaseModel):
    categories: list[FacetCount]
    labels: list[FacetCount]


class NearbyResponse(BaseModel):
    stop_id: str
    total: int
    limit: int
    offset: int
    spots: list[Spot]
    facets: Facets


def public_labels(spot: Spot) -> Spot:
    """Drop every label that is not declared or certified."""
    return spot.model_copy(
        update={"labels": [l for l in spot.labels if l.status in PUBLIC_STATUSES]}
    )


def filter_spots(
    spots: list[Spot],
    *,
    categories: list[str] | None = None,
    labels: list[str] | None = None,
    match: Literal["any", "all"] = "all",
    sponsored: bool | None = None,
    include_demo: bool = True,
    q: str | None = None,
) -> list[Spot]:
    out = []
    needle = q.strip().lower() if q and q.strip() else None
    for s in spots:
        if not include_demo and s.demo:
            continue
        if categories and s.category.slug not in categories:
            continue
        if sponsored is not None and (s.placement_type == "sponsored") != sponsored:
            continue
        if needle and needle not in s.name.lower():
            continue
        if labels:
            have = {l.slug for l in s.labels if l.status in PUBLIC_STATUSES}
            want = set(labels)
            ok = bool(have & want) if match == "any" else want <= have
            if not ok:
                continue
        out.append(s)
    return out


def sort_spots(spots: list[Spot], sort: Literal["distance", "name", "sponsored_first"]) -> list[Spot]:
    if sort == "name":
        return sorted(spots, key=lambda s: s.name.lower())
    if sort == "sponsored_first":
        return sorted(spots, key=lambda s: (s.placement_type != "sponsored", s.name.lower()))
    return sorted(
        spots, key=lambda s: (s.distance_m is None, s.distance_m or 0.0, s.name.lower())
    )


def build_facets(spots: list[Spot]) -> Facets:
    cats: dict[str, FacetCount] = {}
    labs: dict[str, FacetCount] = {}
    for s in spots:
        c = cats.setdefault(s.category.slug, FacetCount(slug=s.category.slug, display_name=s.category.display_name, count=0))
        c.count += 1
        for l in s.labels:
            if l.status in PUBLIC_STATUSES:
                f = labs.setdefault(l.slug, FacetCount(slug=l.slug, display_name=l.display_name, count=0))
                f.count += 1
    return Facets(
        categories=sorted(cats.values(), key=lambda f: f.slug),
        labels=sorted(labs.values(), key=lambda f: f.slug),
    )
