import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from data_platform import ingest, load_static, mbta, migrate

FIX = Path(__file__).parent / "fixtures" / "mbta"
POLL = datetime(2026, 11, 21, 18, 0, tzinfo=timezone.utc)


def _body(name):
    body = json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))
    body.pop("links", None)  # captured with a page limit; the mock serves one page only
    return body


def handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    q = request.url.params
    if path == "/routes":
        return httpx.Response(200, json=_body("routes"))
    if path == "/stops":
        route = q.get("filter[route]")
        body = _body("route_stops") if route == "Red" else {"data": []}
        return httpx.Response(200, json=body)
    if path == "/vehicles":
        return httpx.Response(200, json=_body("vehicles"))
    if path == "/predictions":
        assert q.get("filter[route]"), "predictions require a route filter"
        return httpx.Response(200, json=_body("predictions"))
    if path == "/alerts":
        return httpx.Response(200, json=_body("alerts"))
    return httpx.Response(404, json={"errors": []})


def make_client(h=handler, **kw):
    return mbta.MbtaClient(api_key="k", base_url="https://mbta.test", transport=httpx.MockTransport(h), **kw)


def test_client_sends_api_key_and_retries_on_429():
    calls = []

    def h(request):
        calls.append(request.headers.get("x-api-key"))
        if len(calls) < 3:
            return httpx.Response(429)
        return httpx.Response(200, json={"data": [{"id": "a"}]})

    async def go():
        async with make_client(h, backoff_s=0) as c:
            return await c.get_all("/routes")

    assert asyncio.run(go()) == [{"id": "a"}]
    assert calls == ["k", "k", "k"]


def test_client_follows_next_links():
    def h(request):
        if request.url.params.get("page[offset]") == "1":
            return httpx.Response(200, json={"data": [{"id": "b"}]})
        return httpx.Response(200, json={"data": [{"id": "a"}], "links": {"next": "/routes?page[offset]=1"}})

    async def go():
        async with make_client(h) as c:
            return await c.get_all("/routes")

    assert [r["id"] for r in asyncio.run(go())] == ["a", "b"]


def test_fetch_cycle_without_db():
    async def go():
        async with make_client() as c:
            return await ingest.fetch_cycle(c, ["Red"], POLL)

    data = asyncio.run(go())
    assert len(data["vehicles"]) == 2 and len(data["predictions"]) == 2 and len(data["alerts"]) >= 1
    assert all(v["time"] == POLL for v in data["vehicles"])


def test_fetch_static_without_db():
    async def go():
        async with make_client() as c:
            return await load_static.fetch_static(c)

    routes, stops, route_stops = asyncio.run(go())
    assert {r["id"] for r in routes} >= {"Red"}
    assert stops and route_stops
    red0 = sorted(rs["stop_sequence"] for rs in route_stops if rs["route_id"] == "Red" and rs["direction_id"] == 0)
    assert red0 == list(range(1, len(red0) + 1))


@pytest.fixture
def conn(db_conn):
    migrate.migrate()
    return db_conn


def test_one_cycle_writes_rows_and_load_static_is_idempotent(conn):
    async def static():
        async with make_client() as c:
            return await load_static.fetch_static(c)

    routes, stops, route_stops = asyncio.run(static())
    load_static.write_static(conn, routes, stops, route_stops)
    conn.commit()
    n1 = conn.execute("SELECT count(*) FROM stops").fetchone()[0]
    load_static.write_static(conn, routes, stops, route_stops)
    conn.commit()
    assert conn.execute("SELECT count(*) FROM stops").fetchone()[0] == n1
    rs1 = conn.execute("SELECT count(*) FROM route_stops").fetchone()[0]
    load_static.write_static(conn, routes, stops, route_stops)
    conn.commit()
    assert conn.execute("SELECT count(*) FROM route_stops").fetchone()[0] == rs1

    async def cycle():
        async with make_client() as c:
            return await ingest.run_cycle(c, conn)

    counts = asyncio.run(cycle())
    conn.commit()
    assert counts["vehicles"] == 2 and counts["predictions"] == 2
    assert conn.execute("SELECT count(*) FROM vehicles").fetchone()[0] >= 2
    assert conn.execute("SELECT count(*) FROM alerts").fetchone()[0] >= 1
    assert conn.execute("SELECT count(*) FROM alert_entities").fetchone()[0] >= 1
