"""Response models. Field names and nullability mirror contracts-draft/api/data-platform.yaml."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class Mode(str, Enum):
    subway = "subway"
    light_rail = "light_rail"
    bus = "bus"
    commuter_rail = "commuter_rail"
    ferry = "ferry"


class Route(BaseModel):
    id: str
    short_name: str | None = None
    long_name: str | None = None
    mode: Mode
    route_type: int | None = None
    color: str | None = None
    text_color: str | None = None
    line_id: str | None = None
    sort_order: int | None = None


class Line(BaseModel):
    id: str
    name: str
    mode: Mode | None = None
    color: str | None = None
    route_ids: list[str]
    route_count: int


class Stop(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    parent_station: str | None = None
    municipality: str | None = None
    neighborhood: str | None = None
    wheelchair_boarding: int | None = None
    is_freedom_trail: bool = False
    distance_m: float | None = None


class StopFact(BaseModel):
    id: int
    kind: str
    title: str | None = None
    body: str
    source_url: str | None = None


class StopDetail(Stop):
    routes: list[Route]
    facts: list[StopFact]


class Vehicle(BaseModel):
    vehicle_id: str
    time: datetime
    route_id: str | None = None
    trip_id: str | None = None
    stop_id: str | None = None
    direction_id: int | None = None
    current_status: str | None = None
    lat: float | None = None
    lon: float | None = None
    bearing: float | None = None
    speed: float | None = None
    label: str | None = None
    updated_at: datetime | None = None


class Prediction(BaseModel):
    prediction_id: str
    stop_id: str | None = None
    route_id: str | None = None
    trip_id: str | None = None
    direction_id: int | None = None
    arrival_time: datetime | None = None
    departure_time: datetime | None = None
    status: str | None = None
    schedule_relationship: str | None = None


class Alert(BaseModel):
    id: str
    effect: str | None = None
    cause: str | None = None
    severity: int | None = None
    header: str | None = None
    description: str | None = None
    lifecycle: str | None = None
    active_start: datetime | None = None
    active_end: datetime | None = None
    route_ids: list[str] = []
    stop_ids: list[str] = []
