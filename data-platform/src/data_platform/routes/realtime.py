from fastapi import APIRouter, HTTPException, Query

from .. import db
from ..models import Alert, Prediction, Vehicle

router = APIRouter()


@router.get("/vehicles", response_model=list[Vehicle], operation_id="listVehicles")
def list_vehicles(
    route_id: str | None = None,
    stop_id: str | None = None,
    since_s: int = Query(120, ge=1),
):
    """Latest sample per vehicle within the last since_s seconds. With stop_id the filter
    applies before picking the latest row, i.e. 'seen at this stop within since_s'."""
    where, params = ["time >= now() - make_interval(secs => %(since_s)s)"], {"since_s": since_s}
    if route_id:
        where.append("route_id = %(route_id)s")
        params["route_id"] = route_id
    if stop_id:
        where.append("stop_id = %(stop_id)s")
        params["stop_id"] = stop_id
    sql = ("SELECT DISTINCT ON (vehicle_id) time, vehicle_id, route_id, trip_id, stop_id, direction_id, "
           "current_status, lat, lon, bearing, speed, label, updated_at FROM vehicles "
           f"WHERE {' AND '.join(where)} ORDER BY vehicle_id, time DESC")
    return db.fetch_all(sql, params)


@router.get("/predictions", response_model=list[Prediction], operation_id="listPredictions")
def list_predictions(stop_id: str | None = None, route_id: str | None = None):
    if not stop_id and not route_id:
        raise HTTPException(422, "stop_id or route_id is required")
    where, params = [], {}
    if stop_id:
        where.append("stop_id = %(stop_id)s")
        params["stop_id"] = stop_id
    if route_id:
        where.append("route_id = %(route_id)s")
        params["route_id"] = route_id
    cond = " AND ".join(where)
    # Latest poll that has data for this filter, still-upcoming entries only.
    sql = ("SELECT prediction_id, stop_id, route_id, trip_id, direction_id, arrival_time, "
           "departure_time, status, schedule_relationship FROM predictions "
           f"WHERE {cond} AND time = (SELECT max(time) FROM predictions WHERE {cond}) "
           "AND coalesce(arrival_time, departure_time) >= now() "
           "ORDER BY coalesce(arrival_time, departure_time), prediction_id")
    return db.fetch_all(sql, params)


@router.get("/alerts", response_model=list[Alert], operation_id="listAlerts")
def list_alerts(route_id: str | None = None, stop_id: str | None = None, active: bool = True):
    source = "active_alerts" if active else "alerts"  # fixed choice, not user input
    where, params = [], {}
    if route_id:
        where.append("EXISTS (SELECT 1 FROM alert_entities x WHERE x.alert_id = a.id AND x.route_id = %(route_id)s)")
        params["route_id"] = route_id
    if stop_id:
        where.append("EXISTS (SELECT 1 FROM alert_entities x WHERE x.alert_id = a.id AND x.stop_id = %(stop_id)s)")
        params["stop_id"] = stop_id
    sql = (
        "SELECT a.id, a.effect, a.cause, a.severity, a.header, a.description, a.lifecycle, "
        "a.active_start, a.active_end, "
        "coalesce(array_agg(DISTINCT e.route_id) FILTER (WHERE e.route_id IS NOT NULL), '{}') AS route_ids, "
        "coalesce(array_agg(DISTINCT e.stop_id) FILTER (WHERE e.stop_id IS NOT NULL), '{}') AS stop_ids "
        f"FROM {source} a LEFT JOIN alert_entities e ON e.alert_id = a.id "
        + (f"WHERE {' AND '.join(where)} " if where else "")
        + "GROUP BY a.id, a.effect, a.cause, a.severity, a.header, a.description, a.lifecycle, "
          "a.active_start, a.active_end ORDER BY a.severity DESC NULLS LAST, a.id"
    )
    return db.fetch_all(sql, params)
