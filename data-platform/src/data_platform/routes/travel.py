"""GET /me/travel: miles per line, traveled segments and unlocked spots for one rider.

Read-only SQL over rider_events (hypertable) and the real MBTA route_stops. Definition of "traveled":
two consecutive check-ins/ride events on the same route, at most 3 hours apart, cover every
consecutive-stop segment between them. Miles are straight-line distances between consecutive stops
(an approximation, not track length). Only route directions with unique stop sequences are used, so
branching lines are approximate: segments near a branch point can be missed or joined across the branch. Dev auth: the bearer token is the username (or the user uuid).
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .. import db

router = APIRouter()

SEGMENTS_SQL = """
WITH ev AS (
    SELECT route_id, stop_id, time,
           lag(stop_id) OVER w AS prev_stop, lag(time) OVER w AS prev_time
      FROM rider_events
     WHERE user_id = %(uid)s AND route_id IS NOT NULL AND stop_id IS NOT NULL
       AND event_type IN ('checkin', 'ride_start', 'ride_end')
    WINDOW w AS (PARTITION BY route_id ORDER BY time)),
pairs AS (
    SELECT DISTINCT route_id, prev_stop, stop_id FROM ev
     WHERE prev_stop IS NOT NULL AND prev_stop <> stop_id AND time - prev_time <= interval '3 hours'),
span AS (
    SELECT p.route_id, a.direction_id,
           least(a.stop_sequence, b.stop_sequence) AS lo, greatest(a.stop_sequence, b.stop_sequence) AS hi
      FROM pairs p
      JOIN route_stops a ON a.route_id = p.route_id AND a.stop_id = p.prev_stop
      JOIN route_stops b ON b.route_id = p.route_id AND b.stop_id = p.stop_id AND b.direction_id = a.direction_id
     WHERE a.stop_sequence IS NOT NULL AND b.stop_sequence IS NOT NULL),
ordered AS (
    SELECT route_id, direction_id, stop_id, stop_sequence,
           lead(stop_id) OVER (PARTITION BY route_id, direction_id ORDER BY stop_sequence) AS next_stop,
           lead(stop_sequence) OVER (PARTITION BY route_id, direction_id ORDER BY stop_sequence) AS next_seq
      FROM route_stops rs WHERE stop_sequence IS NOT NULL
       AND (rs.route_id, rs.direction_id) IN (   -- branching patterns repeat sequence numbers; skip those directions
            SELECT route_id, direction_id FROM route_stops WHERE stop_sequence IS NOT NULL
             GROUP BY route_id, direction_id HAVING count(*) = count(DISTINCT stop_sequence))),
segs AS (
    SELECT DISTINCT o.route_id, least(o.stop_id, o.next_stop) AS from_stop, greatest(o.stop_id, o.next_stop) AS to_stop
      FROM ordered o JOIN span s ON s.route_id = o.route_id AND s.direction_id = o.direction_id
     WHERE o.next_stop IS NOT NULL AND o.stop_sequence >= s.lo AND o.next_seq <= s.hi)
SELECT sg.route_id, r.line_id, sg.from_stop, sg.to_stop,
       fs.lat AS from_lat, fs.lon AS from_lon, ts.lat AS to_lat, ts.lon AS to_lon,
       2 * 6371000 * asin(sqrt(power(sin(radians(ts.lat - fs.lat) / 2), 2) +
           cos(radians(fs.lat)) * cos(radians(ts.lat)) * power(sin(radians(ts.lon - fs.lon) / 2), 2))) / 1609.344 AS miles
  FROM segs sg
  JOIN routes r ON r.id = sg.route_id
  JOIN stops fs ON fs.id = sg.from_stop JOIN stops ts ON ts.id = sg.to_stop
 WHERE fs.lat IS NOT NULL AND ts.lat IS NOT NULL
 ORDER BY sg.route_id, sg.from_stop, sg.to_stop
"""

LINES_SQL = """
SELECT id AS line_id, coalesce(long_name, short_name, id) AS name, color FROM lines
 WHERE id IN (SELECT line_id FROM routes WHERE mode IN ('subway', 'light_rail') AND line_id IS NOT NULL)
 ORDER BY sort_order NULLS LAST, id"""

UNLOCKED_SQL = """
SELECT DISTINCT ON (payload->>'spot_id') payload->>'spot_id' AS spot_id, ns.name, e.stop_id,
       (SELECT count(*) FROM stop_content sc WHERE sc.stop_id = e.stop_id) AS fact_count
  FROM rider_events e JOIN nearby_spots ns ON ns.id::text = e.payload->>'spot_id'
 WHERE e.user_id = %(uid)s AND e.event_type = 'visit' AND ns.active AND ns.removed_at IS NULL
 ORDER BY payload->>'spot_id', e.time DESC"""


class LineMiles(BaseModel):
    line_id: str
    name: str
    color: str | None = None
    miles: float


class Segment(BaseModel):
    route_id: str
    line_id: str | None = None
    from_stop_id: str
    to_stop_id: str
    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float
    miles: float


class UnlockedSpot(BaseModel):
    spot_id: str
    name: str
    stop_id: str | None = None
    fact_count: int


class Travel(BaseModel):
    total_miles: float
    per_line: list[LineMiles]
    traveled_segments: list[Segment]
    unlocked_spots: list[UnlockedSpot]


def resolve_user(token: str) -> UUID | None:
    try:
        return UUID(token)
    except ValueError:
        pass
    row = db.fetch_one("SELECT id FROM users WHERE username = %s", (token,))
    return row["id"] if row else None


def build_travel(uid: UUID) -> Travel:
    segs = db.fetch_all(SEGMENTS_SQL, {"uid": uid})
    per_line: dict[str, float] = {}
    for s in segs:
        if s["line_id"]:
            per_line[s["line_id"]] = per_line.get(s["line_id"], 0.0) + s["miles"]
    lines = []
    seen = set()
    for l in db.fetch_all(LINES_SQL):
        seen.add(l["line_id"])
        lines.append(LineMiles(line_id=l["line_id"], name=l["name"], color=l["color"],
                               miles=round(per_line.get(l["line_id"], 0.0), 2)))
    for lid, m in per_line.items():  # lines outside the subway list (bus, commuter rail) that were ridden
        if lid not in seen:
            lines.append(LineMiles(line_id=lid, name=lid, miles=round(m, 2)))
    return Travel(
        total_miles=round(sum(per_line.values()), 2),
        per_line=lines,
        traveled_segments=[Segment(route_id=s["route_id"], line_id=s["line_id"], from_stop_id=s["from_stop"],
                                   to_stop_id=s["to_stop"], from_lat=s["from_lat"], from_lon=s["from_lon"],
                                   to_lat=s["to_lat"], to_lon=s["to_lon"], miles=round(s["miles"], 3))
                           for s in segs],
        unlocked_spots=[UnlockedSpot(spot_id=u["spot_id"], name=u["name"], stop_id=u["stop_id"],
                                     fact_count=u["fact_count"]) for u in db.fetch_all(UNLOCKED_SQL, {"uid": uid})],
    )


@router.get("/me/travel", response_model=Travel, operation_id="myTravel")
def my_travel(authorization: Annotated[str | None, Header()] = None):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    uid = resolve_user(authorization[7:].strip())
    if uid is None:  # a rider with no events yet: zero state, so a new account does not break the screen
        return build_travel(UUID(int=0))
    return build_travel(uid)
