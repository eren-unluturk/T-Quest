"""game-engine HTTP service.

Run (from game-engine/src):  uvicorn game_engine.app:app --port 8003

Storage: set DATABASE_URL to use the shared Tiger Data database (PgStore).
Without it the service keeps everything in memory (demo mode, MemoryStore).
DATABASE MODE IS READ-ONLY BY DEFAULT: writes (POST routes) answer 503
db_writes_disabled unless GE_ALLOW_DB_WRITES=1. With writes on, every user is a
demo user ("demo_" + name) and check-ins are written with is_synthetic = true;
remove it all with `python -m game_engine.demo_reset`. See README.

Auth (demo): "Authorization: Bearer <username>" -- the token IS the username.
Store verify: header "X-Store-Key". Accepted if it equals env STORE_KEY
(default "dev-store-key", memory mode only) or matches the store's sha256 hash.
Live vehicle check: ON by default with the database (a vehicle must be within
VEHICLE_RADIUS_M of the stop in the last 5 minutes; needs the MBTA ingest running).
Set VEHICLE_CHECK=off to skip it. Memory mode skips it.
"""
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import badges, config
from .checkin import validate_checkin
from .points import checkin_points
from .ranks import rank_for, rank_info
from .redemption import RedemptionError
from .social import leaderboard, points_in_period
from .store import MemoryStore

@asynccontextmanager
async def lifespan(_app):
    """Start the delay-bonus loop when the database is on and demo writes are allowed."""
    stop = None
    if os.environ.get("DATABASE_URL") and os.environ.get("GE_ALLOW_DB_WRITES") == "1":
        interval = int(os.environ.get("DELAY_JOB_INTERVAL_S", "300"))
        if interval > 0:
            from .delay_job import start_background
            stop = start_background(interval)
    yield
    if stop is not None:
        stop.set()


app = FastAPI(title="T-Quest game-engine", version="0.2.0", lifespan=lifespan)

# CORS (CORS_ORIGINS; exact origins required when APP_ENV=prod), rate limits, body limit, security headers and
# generic errors come from shared/tquest_http.py, the same hardening every service uses.
from . import _shared  # noqa: E402,F401
import tquest_auth  # noqa: E402
import tquest_http  # noqa: E402

tquest_http.harden(app, extra_headers=("X-Store-Key",))

LOCK = threading.RLock()
_store = None


def get_store():
    global _store
    if _store is None:
        if os.environ.get("DATABASE_URL"):
            from .pg_store import PgStore, connect
            _store = PgStore(connect(), allow_writes=os.environ.get("GE_ALLOW_DB_WRITES") == "1")
        else:
            _store = MemoryStore()
    return _store


def set_store(store):
    """Swap the store (tests)."""
    global _store
    _store = store


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def current_user(authorization: str = Header(default="")):
    try:
        user = tquest_auth.user_from_authorization(authorization)
    except tquest_auth.AuthError:
        raise HTTPException(401, "invalid or missing credentials")
    get_store().ensure_user(user)
    return user


def lifetime_of(entries):
    return sum(e.delta for e in entries if e.delta > 0)


class GpsSample(BaseModel):
    lat: float
    lon: float


class CheckinRequest(BaseModel):
    stop_id: str
    lat: float
    lon: float
    client_time: datetime
    mode: str | None = None
    consent: bool = True  # stand-in until the consent table is wired
    accuracy_m: float | None = None  # reported GPS accuracy; worse than 50 m is refused (poor_gps)
    samples: list[GpsSample] | None = Field(default=None, max_length=10)  # 3 to 10 readings over a few seconds


class FriendRequest(BaseModel):
    username: str


class RedeemRequest(BaseModel):
    offer_id: str


class VerifyRequest(BaseModel):
    code: str
    store_id: str


def redemption_json(r):
    return {"code": r["code"], "offer_id": r["offer_id"], "status": r["status"],
            "expires_at": r["expires_at"].isoformat()}


@app.get("/healthz")
def healthz():
    st = get_store()
    return {"ok": True, "store": st.name, "writes": bool(getattr(st, "can_write", True))}


def require_write(st):
    """Database mode is read-only unless GE_ALLOW_DB_WRITES=1 (demo-safe default)."""
    if not getattr(st, "can_write", True):
        raise HTTPException(503, "db_writes_disabled")


@app.post("/checkins", status_code=201)
def post_checkin(body: CheckinRequest, user: str = Depends(current_user)):
    st = get_store()
    require_write(st)
    stop = st.stop(body.stop_id)
    if stop is None:
        raise HTTPException(404, "unknown stop")
    with LOCK:
        t = now()
        history = st.checkins_at_stop(user, body.stop_id)
        last = history[-1] if history else None
        default_mode = "strict" if st.name == "postgres" else "off"
        if os.environ.get("VEHICLE_CHECK", default_mode) == "strict":
            seen = st.vehicle_seen_at(body.stop_id, t, stop["lat"], stop["lon"])
        else:
            seen = t
        # Speed check (server time only): on by default with the database, off in memory demo mode
        previous = st.last_checkin(user) if os.environ.get("SPEED_CHECK", default_mode) == "strict" else None
        res = validate_checkin(
            consent=body.consent, user_lat=body.lat, user_lon=body.lon,
            stop_lat=stop["lat"], stop_lon=stop["lon"], now=t,
            last_vehicle_seen_at=seen, last_checkin_at=last, previous_checkin=previous,
            accuracy_m=body.accuracy_m,
            samples=[(s.lat, s.lon) for s in body.samples] if body.samples else None)
        if not res.ok:
            raise HTTPException(res.http_status, res.reason)

        first = not history
        day_start = t.replace(hour=0, minute=0, second=0, microsecond=0)
        repeats_today = sum(1 for x in history if x >= day_start)
        entries = st.ledger_entries(user)
        today_pts = sum(e.delta for e in entries
                        if e.at >= day_start and e.reason in ("first_visit", "repeat_visit"))
        pts = checkin_points(first_visit=first, repeats_today_at_stop=repeats_today,
                             checkin_points_today=today_pts)
        old_rank = rank_for(lifetime_of(entries))[0]
        st.record_checkin(user, body.stop_id, body.lat, body.lon, body.client_time, t, pts, body.mode or stop.get("mode"))
        if pts:
            st.add_points(user, t, pts, "first_visit" if first else "repeat_visit")

        extra = 0
        owned = st.badges(user)
        visited = st.visited_stops(user)
        done_quests = {e.reason[6:] for e in st.ledger_entries(user) if e.reason.startswith("quest:")}
        new_badges = set()
        for q in badges.completed_quests(st.quests(), visited, done_quests):
            st.add_points(user, t, q.reward_points, "quest", "quest", q.id)
            extra += q.reward_points
            if q.reward_badge_id and q.reward_badge_id not in owned:
                new_badges.add(q.reward_badge_id)
        rank_now = rank_for(lifetime_of(st.ledger_entries(user)))[0]
        new_badges |= badges.unlocked_badges(visited_stops=visited, rank=rank_now, already_have=owned | new_badges, catalog=st.catalog())
        for b in sorted(new_badges):
            st.add_badge(user, b, t, "checkin")
            if b.startswith("line-"):
                st.add_points(user, t, config.COMPLETE_LINE_POINTS, "complete_line", "badge", b)
                extra += config.COMPLETE_LINE_POINTS
        final_rank = rank_for(lifetime_of(st.ledger_entries(user)))[0]
        return {"checkin_id": f"{user}-{len(history) + 1}-{body.stop_id}",
                "points_awarded": pts + extra, "first_visit": first,
                "new_rank": final_rank if final_rank != old_rank else None,
                "badges_unlocked": sorted(new_badges)}


class SpotVisitRequest(BaseModel):
    stop_id: str | None = None  # the station the rider was looking at; default: the spot's nearest station


@app.post("/spots/{spot_id}/visit", status_code=201)
def post_spot_visit(spot_id: str, response: Response, body: SpotVisitRequest = SpotVisitRequest(),
                    user: str = Depends(current_user)):
    """A rider tapped a spot: save one 'visit' rider event with payload.spot_id (once per spot per day).

    No points. Spots are placeholder places near stations (insights-sponsors tables).
    """
    st = get_store()
    require_write(st)
    stops = st.spot_stops(spot_id)
    if stops is None:
        raise HTTPException(404, "unknown spot")
    if body.stop_id is not None:
        if body.stop_id not in stops:
            raise HTTPException(422, "spot_not_near_stop")
        stop_id = body.stop_id
    elif stops:
        stop_id = min(stops, key=lambda s: (stops[s] is None, stops[s] or 0.0))
    else:
        raise HTTPException(422, "spot_has_no_stop")
    with LOCK:
        t = now()
        day_start = t.replace(hour=0, minute=0, second=0, microsecond=0)
        if st.spot_visited_since(user, spot_id, day_start):
            response.status_code = 200
            return {"spot_id": spot_id, "stop_id": stop_id, "visited_at": None, "already_visited_today": True}
        st.record_spot_visit(user, spot_id, stop_id, t)
    return {"spot_id": spot_id, "stop_id": stop_id, "visited_at": t.isoformat(), "already_visited_today": False}


@app.get("/me/points")
def get_points(user: str = Depends(current_user)):
    entries = get_store().ledger_entries(user)
    recent = [{"at": e.at.isoformat(), "delta": e.delta, "reason": e.reason}
              for e in reversed(entries[-20:])]
    return {"balance": sum(e.delta for e in entries), "lifetime": lifetime_of(entries), "recent": recent}


@app.get("/me/rank")
def get_rank(user: str = Depends(current_user)):
    return rank_info(lifetime_of(get_store().ledger_entries(user)))


@app.get("/me/collection")
def get_collection(user: str = Depends(current_user)):
    st = get_store()
    owned = st.badges(user)
    return {"stops": sorted(st.visited_stops(user)), "badges": sorted(owned),
            "physical_rewards": st.physical_rewards_for(owned)}


@app.get("/quests")
def get_quests(user: str = Depends(current_user)):
    return [{"id": q.id, "title": q.title, "sponsor_id": q.sponsor_id,
             "goal": (f"Visit {q.min_stops} different stations" if q.min_stops
                      else "Visit: " + ", ".join(sorted(q.goal_stops))),
             "reward_points": q.reward_points, "reward_badge_id": q.reward_badge_id}
            for q in get_store().quests()]


@app.get("/leaderboards")
def get_leaderboards(scope: str = "global", period: str = "all",
                     user: str = Depends(current_user)):
    if scope not in ("global", "friends"):
        raise HTTPException(422, "scope must be global or friends (line needs route data)")
    if period not in ("week", "month", "all"):
        raise HTTPException(422, "period must be week, month or all")
    st = get_store()
    t = now()
    scores = {u: points_in_period(es, period, t) for u, es in st.all_ledgers().items()}
    friends = st.friends(user)
    for name in [user, *friends]:
        scores.setdefault(name, 0)
    return leaderboard(scores, scope=scope, me=user, friends=friends)


@app.get("/friends")
def get_friends(user: str = Depends(current_user)):
    st = get_store()
    return [{"username": f, "rank": rank_for(lifetime_of(st.ledger_entries(f)))[0]} for f in st.friends(user)]


@app.post("/friends", status_code=201)
def post_friend(body: FriendRequest, user: str = Depends(current_user)):
    st = get_store()
    require_write(st)
    with LOCK:
        if body.username != user:
            st.ensure_user(body.username)
        result = st.add_friend(user, body.username)
    if result == "self":
        raise HTTPException(422, "cannot_friend_self")
    if result == "exists":
        raise HTTPException(409, "already_friends")
    return {"username": body.username}


@app.post("/redemptions", status_code=201)
def post_redemption(body: RedeemRequest, user: str = Depends(current_user)):
    st = get_store()
    require_write(st)
    offer = st.offer(body.offer_id)
    if offer is None:
        raise HTTPException(404, "unknown offer")
    with LOCK:
        entries = st.ledger_entries(user)
        try:
            red = st.issue_redemption(user=user, offer_id=body.offer_id, offer=offer,
                                      user_rank=rank_for(lifetime_of(entries))[0],
                                      balance=sum(e.delta for e in entries), now=now())
        except RedemptionError as e:
            raise HTTPException(e.http_status, e.reason)
    return redemption_json(red)


@app.post("/redemptions/verify")
def verify_redemption(body: VerifyRequest, x_store_key: str = Header(default="")):
    st = get_store()
    require_write(st)
    demo_key = os.environ.get("STORE_KEY", "dev-store-key" if st.name == "memory" else "")
    key_ok = bool(demo_key) and x_store_key == demo_key
    if not key_ok and not (hasattr(st, "store_key_ok") and st.store_key_ok(body.store_id, x_store_key)):
        raise HTTPException(401, "bad store key")
    with LOCK:
        try:
            red = st.verify_redemption(code=body.code, store_id=body.store_id,
                                       store_key=x_store_key, now=now())
        except RedemptionError as e:
            raise HTTPException(e.http_status, e.reason)
    return redemption_json(red)
