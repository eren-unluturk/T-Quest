"""Pydantic models. Names and fields match openapi/insights-sponsors.yaml.

Internal models (Stop, Sponsor, RewardStore, WeekBucket, TopStop) back inline
or non-API shapes.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["food", "clothing", "sports", "other"]
ConsentScope = Literal["location", "place_visits"]


class Error(BaseModel):
    detail: str


class PolicyMismatch(BaseModel):
    detail: str
    current: str


class Stop(BaseModel):
    """Internal: a seeded MBTA stop."""

    id: str
    name: str
    lat: float
    lon: float
    neighborhood: str
    mode: Literal["subway", "bus"] = "subway"


class Sponsor(BaseModel):
    """Internal: a (fictional demo) sponsor."""

    id: str
    name: str
    category: str = "other"
    demo_placeholder: bool = True


class Fact(BaseModel):
    id: str
    kind: Literal["fast_fact", "history", "freedom_trail"]
    title: str
    body: str
    source_url: str | None = None


class StopFacts(BaseModel):
    stop_id: str
    stop_name: str
    facts: list[Fact]


class StorePartner(BaseModel):
    id: str
    name: str
    category: Category
    lat: float
    lon: float
    nearest_stop_id: str
    address: str


class Offer(BaseModel):
    id: str
    sponsor_id: str
    store_id: str | None = None
    title: str
    description: str
    kind: Literal["discount", "free_item", "points_item"]
    discount_pct: int | None = None
    points_cost: int | None = None
    min_rank: int
    required_badge_id: str | None = None
    per_user_limit: int
    starts_at: datetime
    ends_at: datetime | None = None
    placement: Literal["local_pick", "sponsored_quest"]
    demo: bool = True


class LocalPick(BaseModel):
    store: StorePartner
    offers: list[Offer]
    distance_m: float


class TrailSite(BaseModel):
    id: str
    order: int
    name: str
    lat: float
    lon: float
    nearest_stop_id: str
    blurb: str


class FunFact(BaseModel):
    id: str
    body: str
    tags: list[str]


class RewardStore(BaseModel):
    store_id: str
    in_stock: bool


class PhysicalReward(BaseModel):
    id: str
    kind: Literal["sticker", "patch"]
    name: str
    description: str
    badge_id: str
    min_rank: int
    per_user_limit: int
    image_url: str | None = None
    stores: list[RewardStore]


class Recommendation(BaseModel):
    kind: Literal["route", "neighborhood", "stop"]
    id: str
    title: str
    reason: str
    score: float
    sponsored: bool
    sponsor_id: str | None = None


class Recommendations(BaseModel):
    generated_at: datetime
    items: list[Recommendation]


class WeekBucket(BaseModel):
    week_start: date
    checkins: int
    unique_stops: int


class TopStop(BaseModel):
    stop_id: str
    visits: int


class MyAnalytics(BaseModel):
    user_id: str
    period: Literal["week", "month", "all"]
    stops_visited: int
    unique_stops: int
    lines_ridden: list[str]
    home_line: str | None = None
    by_week: list[WeekBucket]
    top_stops: list[TopStop]
    neighborhoods_explored: list[str]


class Consent(BaseModel):
    scope: ConsentScope
    granted: bool
    granted_at: datetime | None = None
    revoked_at: datetime | None = None
    policy_version: str


class ConsentRequest(BaseModel):
    scope: ConsentScope
    policy_version: str


class RiderEvent(BaseModel):
    """Internal: one row of rider_events (read side)."""

    time: datetime
    user_id: str
    event_type: str
    stop_id: str | None = None
    route_id: str | None = None
    mode: str | None = None


class PlaceVisit(BaseModel):
    """Internal: one row of place_visits. Only readable with place_visits consent."""

    time: datetime
    user_id: str
    lat: float
    lon: float
    place_category: str
    store_id: str | None = None


class BusiestStop(BaseModel):
    stop_id: str
    stop_name: str
    checkins: int


class TrendingNeighborhood(BaseModel):
    neighborhood: str
    checkins: int
    change_pct: float


class DayCount(BaseModel):
    day: date
    checkins: int


class LineActivity(BaseModel):
    route_id: str
    checkins: int
    by_day: list[DayCount]


class BostonAnalytics(BaseModel):
    period: Literal["week", "month"]
    generated_at: datetime
    total_checkins: int
    active_riders: int
    busiest_stops: list[BusiestStop]
    trending_neighborhoods: list[TrendingNeighborhood]
    lines: list[LineActivity]


class PlaceVisitIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    visited_at: datetime
    place_category: Category
    store_id: str | None = None


class PlaceVisitAck(BaseModel):
    accepted: bool
    retained_days: int


class PlaceVisitsDeleted(BaseModel):
    deleted: int
