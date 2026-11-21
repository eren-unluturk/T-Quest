"""Load MBTA routes, stops and route_stops. Usage: python -m data_platform.load_static"""
import asyncio
import sys

from . import db, mbta

ROUTE_TYPES = "0,1,3"  # light rail, subway, bus
CONCURRENCY = 10


async def fetch_static(client: mbta.MbtaClient) -> tuple[list[dict], list[dict], list[dict]]:
    """Return (routes, stops, route_stops) parsed from the MBTA API."""
    route_res = await client.get_all("/routes", {"filter[type]": ROUTE_TYPES})
    routes = [mbta.parse_route(r) for r in route_res]

    sem = asyncio.Semaphore(CONCURRENCY)
    stops: dict[str, dict] = {}
    route_stops: dict[tuple, dict] = {}

    async def one(route: dict, direction: int) -> None:
        # Rail: parent stations. Bus: plain stops.
        location_type = 1 if route["mode"] in ("subway", "light_rail") else 0
        params = {
            "filter[route]": route["id"],
            "filter[direction_id]": direction,
            "filter[location_type]": location_type,
        }
        async with sem:
            res = await client.get_all("/stops", params)
        for seq, r in enumerate(res, start=1):
            stop = mbta.parse_stop(r)
            if stop["lat"] is None or stop["lon"] is None:
                continue
            stops[stop["id"]] = stop
            route_stops[(route["id"], stop["id"], direction)] = {
                "route_id": route["id"],
                "stop_id": stop["id"],
                "direction_id": direction,
                "stop_sequence": seq,
            }

    await asyncio.gather(*(one(r, d) for r in routes for d in (0, 1)))
    return routes, list(stops.values()), list(route_stops.values())


UPSERT_ROUTE = """
INSERT INTO routes (id, short_name, long_name, mode, route_type, color, text_color, line_id, sort_order)
VALUES (%(id)s, %(short_name)s, %(long_name)s, %(mode)s, %(route_type)s, %(color)s,
        %(text_color)s, %(line_id)s, %(sort_order)s)
ON CONFLICT (id) DO UPDATE SET
    short_name = EXCLUDED.short_name, long_name = EXCLUDED.long_name, mode = EXCLUDED.mode,
    route_type = EXCLUDED.route_type, color = EXCLUDED.color, text_color = EXCLUDED.text_color,
    line_id = EXCLUDED.line_id, sort_order = EXCLUDED.sort_order
"""

# is_freedom_trail and neighborhood are curated, so the loader never overwrites them.
UPSERT_STOP = """
INSERT INTO stops (id, name, lat, lon, parent_station, location_type, municipality, wheelchair_boarding)
VALUES (%(id)s, %(name)s, %(lat)s, %(lon)s, %(parent_station)s, %(location_type)s,
        %(municipality)s, %(wheelchair_boarding)s)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name, lat = EXCLUDED.lat, lon = EXCLUDED.lon,
    parent_station = EXCLUDED.parent_station, location_type = EXCLUDED.location_type,
    municipality = EXCLUDED.municipality, wheelchair_boarding = EXCLUDED.wheelchair_boarding,
    updated_at = now()
"""

UPSERT_ROUTE_STOP = """
INSERT INTO route_stops (route_id, stop_id, direction_id, stop_sequence)
VALUES (%(route_id)s, %(stop_id)s, %(direction_id)s, %(stop_sequence)s)
ON CONFLICT (route_id, stop_id, direction_id) DO UPDATE SET stop_sequence = EXCLUDED.stop_sequence
"""


# stops.mode (added in 0005): primary mode of each stop, rail preferred over bus.
BACKFILL_STOP_MODE = """
UPDATE stops s
   SET mode = x.mode
  FROM (SELECT DISTINCT ON (rs.stop_id) rs.stop_id, r.mode
          FROM route_stops rs
          JOIN routes r ON r.id = rs.route_id
         WHERE r.mode IS NOT NULL
         ORDER BY rs.stop_id,
                  CASE r.mode WHEN 'subway' THEN 1 WHEN 'light_rail' THEN 2
                              WHEN 'commuter_rail' THEN 3 WHEN 'ferry' THEN 4 ELSE 5 END) x
 WHERE s.id = x.stop_id AND s.mode IS DISTINCT FROM x.mode
"""


def write_static(conn, routes: list[dict], stops: list[dict], route_stops: list[dict]) -> None:
    with conn.transaction():
        with conn.cursor() as cur:
            cur.executemany(UPSERT_ROUTE, routes)
            cur.executemany(UPSERT_STOP, stops)
            cur.executemany(UPSERT_ROUTE_STOP, route_stops)
            cur.execute(BACKFILL_STOP_MODE)


async def run() -> dict:
    async with mbta.MbtaClient() as client:
        routes, stops, route_stops = await fetch_static(client)
    with db.connect() as conn:
        write_static(conn, routes, stops, route_stops)
    counts = {"routes": len(routes), "stops": len(stops), "route_stops": len(route_stops)}
    print(counts)
    return counts


if __name__ == "__main__":
    asyncio.run(run())
    sys.exit(0)
