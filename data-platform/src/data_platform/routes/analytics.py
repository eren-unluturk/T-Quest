"""GET /analytics/system: a live snapshot of the MBTA subway from data we collect (read-only, public).

Every number is computed on request from Tiger Data: the live `vehicles` hypertable (last few minutes), the
`vehicles_route_5m` continuous aggregate (vehicle position reports per route per 5 minutes) and `active_alerts`.
"Reports" are vehicle position reports from the MBTA feed, so more reports means more vehicles running.
Nothing here is rider data; the demo-rider insights come from other services and are labeled demo there.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Query
from psycopg.rows import dict_row
from pydantic import BaseModel

from .. import db

router = APIRouter()

TZ = "America/New_York"
SUBWAY_LINES = """
    SELECT l.id AS line_id, coalesce(l.long_name, l.short_name, l.id) AS name, l.color
      FROM lines l
     WHERE l.id IN (SELECT line_id FROM routes WHERE mode IN ('subway', 'light_rail') AND line_id IS NOT NULL)
     ORDER BY l.sort_order NULLS LAST, l.id"""

NOW_SQL = """
    SELECT r.line_id, count(DISTINCT v.vehicle_id) AS vehicles
      FROM vehicles v JOIN routes r ON r.id = v.route_id
     WHERE v.time > now() - interval '5 minutes' AND r.line_id IS NOT NULL
     GROUP BY r.line_id"""

SERIES_SQL = """
    SELECT r.line_id, time_bucket('1 hour', c.bucket) AS hour, sum(c.reports)::int AS reports
      FROM vehicles_route_5m c JOIN routes r ON r.id = c.route_id
     WHERE c.bucket >= date_trunc('hour', now()) - make_interval(hours => %(hours)s) AND r.line_id IS NOT NULL
     GROUP BY r.line_id, hour ORDER BY r.line_id, hour"""

PROFILE_SQL = """
    WITH per_hour AS (
        SELECT (c.bucket AT TIME ZONE %(tz)s)::date AS day,
               extract(hour FROM c.bucket AT TIME ZONE %(tz)s)::int AS hr,
               sum(c.reports) AS reports, count(DISTINCT c.bucket) AS buckets
          FROM vehicles_route_5m c JOIN routes r ON r.id = c.route_id
         WHERE c.bucket >= now() - interval '3 days' AND r.mode IN ('subway', 'light_rail')
           AND c.bucket < date_trunc('hour', now())
         GROUP BY 1, 2)
    SELECT hr, avg(reports)::float AS avg_reports, count(*) AS days
      FROM per_hour WHERE buckets >= 12 GROUP BY hr ORDER BY hr"""

LAST_DAY_SQL = """
    SELECT r.line_id, sum(c.reports)::int AS reports
      FROM vehicles_route_5m c JOIN routes r ON r.id = c.route_id
     WHERE c.bucket >= now() - interval '24 hours' AND r.line_id IS NOT NULL
     GROUP BY r.line_id"""

ALERT_LINES_SQL = """
    SELECT DISTINCT r.line_id
      FROM active_alerts a JOIN alert_entities e ON e.alert_id = a.id JOIN routes r ON r.id = e.route_id
     WHERE r.line_id IS NOT NULL"""


class HourPoint(BaseModel):
    hour: datetime
    reports: int
    partial: bool  # the current hour is still filling


class LineActivity(BaseModel):
    line_id: str
    name: str
    color: str | None = None
    vehicles_now: int
    reports_24h: int
    series: list[HourPoint]


class HourOfDay(BaseModel):
    hour: int  # 0-23, Boston time
    avg_reports: float
    days: int  # complete days this average covers


class SystemSnapshot(BaseModel):
    generated_at: datetime
    last_vehicle_at: datetime | None
    freshness_s: int | None
    active_alerts: int
    lines_with_alerts: list[str]
    lines: list[LineActivity]
    hourly_profile: list[HourOfDay]
    busiest_hour: int | None
    quietest_hour: int | None  # among hours of service with complete data
    busiest_line_24h: str | None
    quietest_line_24h: str | None


def extremes(profile: list[HourOfDay]) -> tuple[int | None, int | None]:
    """(busiest hour, quietest hour) among hours of service (at least one report on average)."""
    served = [p for p in profile if p.avg_reports > 0]
    if not served:
        return None, None
    return max(served, key=lambda p: p.avg_reports).hour, min(served, key=lambda p: p.avg_reports).hour


def line_extremes(totals: dict[str, int]) -> tuple[str | None, str | None]:
    active = {k: v for k, v in totals.items() if v > 0}
    if not active:
        return None, None
    return max(active, key=active.get), min(active, key=active.get)


LAST_SQL = "SELECT max(time) AS t FROM vehicles WHERE time > now() - interval '1 day'"
ALERTS_SQL = "SELECT count(*) AS n FROM active_alerts"


def _run_all(queries):
    """Run several read queries in ONE round trip (psycopg pipeline) on one connection."""
    with db.connect(row_factory=dict_row) as conn:
        with conn.pipeline():
            cursors = [conn.execute(sql, params) for sql, params in queries]
        return [cur.fetchall() for cur in cursors]


@router.get("/analytics/system", response_model=SystemSnapshot, operation_id="getSystemAnalytics")
def system_snapshot(hours: int = Query(6, ge=1, le=24)) -> SystemSnapshot:
    now = datetime.now(timezone.utc)
    lines, now_rows, day_rows, series_rows, profile_rows, last_rows, alert_line_rows, alert_n = _run_all([
        (SUBWAY_LINES, None), (NOW_SQL, None), (LAST_DAY_SQL, None), (SERIES_SQL, {"hours": hours}),
        (PROFILE_SQL, {"tz": TZ}), (LAST_SQL, None), (ALERT_LINES_SQL, None), (ALERTS_SQL, None)])
    line_ids = {x["line_id"] for x in lines}
    now_counts = {r["line_id"]: r["vehicles"] for r in now_rows}
    day_totals = {r["line_id"]: r["reports"] for r in day_rows}
    series: dict[str, list[HourPoint]] = {}
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    for r in series_rows:
        series.setdefault(r["line_id"], []).append(
            HourPoint(hour=r["hour"], reports=r["reports"], partial=r["hour"] >= current_hour))
    profile = [HourOfDay(hour=r["hr"], avg_reports=round(r["avg_reports"], 1), days=r["days"]) for r in profile_rows]
    last_t = last_rows[0]["t"] if last_rows else None
    busiest_h, quietest_h = extremes(profile)
    sub_totals = {l["line_id"]: day_totals.get(l["line_id"], 0) for l in lines}
    busiest_l, quietest_l = line_extremes(sub_totals)
    return SystemSnapshot(
        generated_at=now, last_vehicle_at=last_t,
        freshness_s=int((now - last_t).total_seconds()) if last_t else None,
        active_alerts=alert_n[0]["n"],
        lines_with_alerts=[r["line_id"] for r in alert_line_rows if r["line_id"] in line_ids],
        lines=[LineActivity(line_id=l["line_id"], name=l["name"], color=l["color"],
                            vehicles_now=now_counts.get(l["line_id"], 0), reports_24h=sub_totals[l["line_id"]],
                            series=series.get(l["line_id"], [])) for l in lines],
        hourly_profile=profile, busiest_hour=busiest_h, quietest_hour=quietest_h,
        busiest_line_24h=busiest_l, quietest_line_24h=quietest_l)
