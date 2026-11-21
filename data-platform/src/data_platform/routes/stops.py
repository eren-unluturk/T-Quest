import math

from fastapi import APIRouter, HTTPException, Query

from .. import db
from ..models import Stop, StopDetail

router = APIRouter()

STOP_COLS = ("s.id, s.name, s.lat, s.lon, s.parent_station, s.municipality, s.neighborhood, "
             "s.wheelchair_boarding, s.is_freedom_trail")
M_PER_DEG_LAT = 111_320.0

# Great-circle distance in metres between (s.lat, s.lon) and (%(lat)s, %(lon)s).
HAVERSINE = (
    "2 * 6371000 * asin(sqrt("
    "power(sin(radians(s.lat - %(lat)s) / 2), 2) + "
    "cos(radians(%(lat)s)) * cos(radians(s.lat)) * power(sin(radians(s.lon - %(lon)s) / 2), 2)))"
)


@router.get("/stops", response_model=list[Stop], operation_id="listStops")
def list_stops(
    route_id: str | None = None,
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    radius_m: int = Query(500, ge=1),
    limit: int = Query(50, ge=1, le=500),
):
    if (lat is None) != (lon is None):
        raise HTTPException(422, "lat and lon must be given together")

    where, params = [], {"limit": limit}
    if route_id:
        where.append("s.id IN (SELECT stop_id FROM route_stops WHERE route_id = %(route_id)s)")
        params["route_id"] = route_id

    if lat is not None:
        # Bounding box first (cheap, uses the (lat, lon) index), then exact distance.
        dlat = radius_m / M_PER_DEG_LAT
        dlon = radius_m / (M_PER_DEG_LAT * max(math.cos(math.radians(lat)), 0.01))
        where.append("s.lat BETWEEN %(lat_min)s AND %(lat_max)s AND s.lon BETWEEN %(lon_min)s AND %(lon_max)s")
        params.update(lat=lat, lon=lon, radius_m=radius_m,
                      lat_min=lat - dlat, lat_max=lat + dlat, lon_min=lon - dlon, lon_max=lon + dlon)
        sql = (f"SELECT * FROM (SELECT {STOP_COLS}, {HAVERSINE} AS distance_m FROM stops s "
               f"WHERE {' AND '.join(where)}) q WHERE distance_m <= %(radius_m)s "
               "ORDER BY distance_m, id LIMIT %(limit)s")
    else:
        sql = f"SELECT {STOP_COLS}, NULL::float AS distance_m FROM stops s"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY s.name, s.id LIMIT %(limit)s"
    return db.fetch_all(sql, params)


@router.get("/stops/{id}", response_model=StopDetail, operation_id="getStop")
def get_stop(id: str):
    stop = db.fetch_one(
        f"SELECT {STOP_COLS}, NULL::float AS distance_m FROM stops s WHERE s.id = %s", (id,))
    if stop is None:
        raise HTTPException(404, f"stop {id!r} not found")
    stop["routes"] = db.fetch_all(
        "SELECT DISTINCT r.id, r.short_name, r.long_name, r.mode, r.route_type, r.color, "
        "r.text_color, r.line_id, r.sort_order FROM routes r "
        "JOIN route_stops rs ON rs.route_id = r.id WHERE rs.stop_id = %s "
        "ORDER BY r.sort_order NULLS LAST, r.id", (id,))
    stop["facts"] = db.fetch_all(
        "SELECT id, kind, title, body, source_url FROM stop_facts WHERE stop_id = %s ORDER BY id", (id,))
    return stop
