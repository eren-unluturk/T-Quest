"""MBTA V3 API client (JSON:API) and pure parse functions.

Parse functions turn one JSON:API resource into a dict whose keys match the
columns of the target table.
"""
import asyncio
import json
import os
from datetime import datetime

import httpx

MODE_BY_ROUTE_TYPE = {0: "light_rail", 1: "subway", 2: "commuter_rail", 3: "bus", 4: "ferry"}
RETRY_STATUS = {429, 500, 502, 503, 504}


class MbtaClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        retries: int = 4,
        backoff_s: float = 1.0,
    ):
        api_key = api_key if api_key is not None else os.environ.get("MBTA_API_KEY", "")
        base_url = base_url or os.environ.get("MBTA_API_BASE") or "https://api-v3.mbta.com"
        headers = {"x-api-key": api_key} if api_key else {}
        self._http = httpx.AsyncClient(
            base_url=base_url, headers=headers, transport=transport, timeout=30.0
        )
        self._retries = retries
        self._backoff_s = backoff_s

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "MbtaClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    async def _get(self, path: str, params: dict | None = None) -> dict:
        for attempt in range(self._retries + 1):
            try:
                resp = await self._http.get(path, params=params)
            except httpx.TransportError:
                if attempt == self._retries:
                    raise
            else:
                if resp.status_code not in RETRY_STATUS:
                    resp.raise_for_status()
                    return resp.json()
                if attempt == self._retries:
                    resp.raise_for_status()
            await asyncio.sleep(self._backoff_s * (2 ** attempt))
        raise RuntimeError("unreachable")

    async def get_all(self, path: str, params: dict | None = None) -> list[dict]:
        """GET a collection and follow links.next; returns the combined `data` list."""
        out: list[dict] = []
        body = await self._get(path, params)
        out.extend(body.get("data", []))
        while body.get("links", {}).get("next"):
            body = await self._get(body["links"]["next"])
            out.extend(body.get("data", []))
        return out


# ------------------------------------------------------------------ parsing
def _rel_id(resource: dict, name: str) -> str | None:
    data = (resource.get("relationships") or {}).get(name, {}).get("data")
    return data.get("id") if data else None


def _ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def parse_route(res: dict) -> dict:
    a = res["attributes"]
    return {
        "id": res["id"],
        "short_name": a.get("short_name") or None,
        "long_name": a.get("long_name") or None,
        "mode": MODE_BY_ROUTE_TYPE.get(a.get("type")),
        "route_type": a.get("type"),
        "color": a.get("color"),
        "text_color": a.get("text_color"),
        "line_id": _rel_id(res, "line"),
        "sort_order": a.get("sort_order"),
    }


def parse_stop(res: dict) -> dict:
    a = res["attributes"]
    return {
        "id": res["id"],
        "name": a.get("name"),
        "lat": a.get("latitude"),
        "lon": a.get("longitude"),
        "parent_station": _rel_id(res, "parent_station"),
        "location_type": a.get("location_type"),
        "municipality": a.get("municipality"),
        "wheelchair_boarding": a.get("wheelchair_boarding"),
    }


def parse_vehicle(res: dict, poll_time: datetime) -> dict:
    a = res["attributes"]
    return {
        "time": poll_time,
        "vehicle_id": res["id"],
        "route_id": _rel_id(res, "route"),
        "trip_id": _rel_id(res, "trip"),
        "stop_id": _rel_id(res, "stop"),
        "direction_id": a.get("direction_id"),
        "current_status": a.get("current_status"),
        "lat": a.get("latitude"),
        "lon": a.get("longitude"),
        "bearing": a.get("bearing"),
        "speed": a.get("speed"),
        "label": a.get("label"),
        "updated_at": _ts(a.get("updated_at")),
    }


def parse_prediction(res: dict, poll_time: datetime) -> dict:
    a = res["attributes"]
    return {
        "time": poll_time,
        "prediction_id": res["id"],
        "stop_id": _rel_id(res, "stop"),
        "route_id": _rel_id(res, "route"),
        "trip_id": _rel_id(res, "trip"),
        "direction_id": a.get("direction_id"),
        "arrival_time": _ts(a.get("arrival_time")),
        "departure_time": _ts(a.get("departure_time")),
        "status": a.get("status"),
        "schedule_relationship": a.get("schedule_relationship"),
    }


def parse_alert(res: dict) -> dict:
    a = res["attributes"]
    periods = a.get("active_period") or []
    starts = [_ts(p.get("start")) for p in periods if p.get("start")]
    ends = [_ts(p.get("end")) for p in periods]
    # An open-ended period (end null) means the alert has no end.
    active_end = None if (not ends or any(e is None for e in ends)) else max(ends)
    entities = [
        {
            "route_id": e.get("route"),
            "stop_id": e.get("stop"),
            "route_type": e.get("route_type"),
            "direction_id": e.get("direction_id"),
        }
        for e in (a.get("informed_entity") or [])
    ]
    return {
        "id": res["id"],
        "effect": a.get("effect"),
        "cause": a.get("cause"),
        "severity": a.get("severity"),
        "header": a.get("header"),
        "description": a.get("description"),
        "lifecycle": a.get("lifecycle"),
        "active_start": min(starts) if starts else None,
        "active_end": active_end,
        "raw": json.dumps(a),
        "entities": entities,
    }
