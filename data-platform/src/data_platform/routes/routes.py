from fastapi import APIRouter, Query

from .. import db
from ..models import Line, Mode, Route

router = APIRouter()

ROUTE_COLS = "id, short_name, long_name, mode, route_type, color, text_color, line_id, sort_order"


@router.get("/routes", response_model=list[Route], operation_id="listRoutes")
def list_routes(mode: Mode | None = Query(None)):
    sql = f"SELECT {ROUTE_COLS} FROM routes"
    params: list = []
    if mode:
        sql += " WHERE mode = %s"
        params.append(mode.value)
    sql += " ORDER BY sort_order NULLS LAST, id"
    return db.fetch_all(sql, params)


@router.get("/lines", response_model=list[Line], operation_id="listLines")
def list_lines():
    """Rail routes grouped by line_id (a route without a line_id is its own line);
    all bus routes are summarised as one `bus` group."""
    rows = db.fetch_all(f"SELECT {ROUTE_COLS} FROM routes ORDER BY sort_order NULLS LAST, id")
    groups: dict[str, list[dict]] = {}
    bus: list[dict] = []
    for r in rows:
        if r["mode"] == "bus":
            bus.append(r)
        else:
            groups.setdefault(r["line_id"] or r["id"], []).append(r)

    lines = []
    for key, rs in groups.items():
        if len(rs) == 1:
            name = rs[0]["long_name"] or rs[0]["short_name"] or key
        elif key.startswith("line-"):
            name = f"{key[len('line-'):]} Line"
        else:
            name = key
        lines.append({
            "id": key, "name": name, "mode": rs[0]["mode"], "color": rs[0]["color"],
            "route_ids": [r["id"] for r in rs], "route_count": len(rs),
        })
    if bus:
        lines.append({
            "id": "bus", "name": "Bus", "mode": "bus", "color": None,
            "route_ids": [r["id"] for r in bus], "route_count": len(bus),
        })
    return lines
