"""game-engine HTTP service with IN-MEMORY data (demo mode).

Run (from game-engine/src):  uvicorn game_engine.app:app --port 8003

Auth (demo): "Authorization: Bearer <username>" -- the token IS the username.
Store verify uses header "X-Store-Key" (env STORE_KEY, default "dev-store-key").
Everything here is replaced by Tiger Data tables once data-platform ships them.
"""
import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from . import badges, config
from .checkin import validate_checkin
from .points import Ledger, checkin_points
from .ranks import rank_for, rank_info
from .redemption import RedemptionBook, RedemptionError
from .social import FriendBook, FriendError, leaderboard, points_in_period

app = FastAPI(title="T-Quest game-engine", version="0.1.0")

STORE_KEY = os.environ.get("STORE_KEY", "dev-store-key")

# ---- FAKE reference data (replace with data-platform tables) ----
STOPS = {
    "park": {"lat": 42.3564, "lon": -71.0624, "mode": "subway"},
    "harvard": {"lat": 42.3736, "lon": -71.1190, "mode": "subway"},
    "alewife": {"lat": 42.3954, "lon": -71.1425, "mode": "subway"},
    "downtown": {"lat": 42.3555, "lon": -71.0602, "mode": "subway"},
    "south-station": {"lat": 42.3519, "lon": -71.0552, "mode": "subway"},
}
# Demo: every stop always has a vehicle nearby. Real data comes from MBTA ingestion.
VEHICLE_ALWAYS_SEEN = True

OFFERS = {
    "o1": {"store_id": "s1", "title": "5% off a coffee", "min_rank": 1},
    "o2": {"store_id": "s2", "title": "Free cookie", "min_rank": 5},
}
QUESTS = [
    badges.Quest("q1", "Downtown loop", frozenset({"park", "downtown"}), 40, None, "sponsor1"),
]

# ---- in-memory per-user state ----
LEDGERS = {}
VISITS = {}     # user -> {stop_id: [datetime, ...]}
BADGES = {}     # user -> set
DONE_QUESTS = {}
FRIENDS = FriendBook()
BOOK = RedemptionBook()


def reset():
    """Clear all demo state (used by tests)."""
    global FRIENDS, BOOK
    LEDGERS.clear()
    VISITS.clear()
    BADGES.clear()
    DONE_QUESTS.clear()
    FRIENDS = FriendBook()
    BOOK = RedemptionBook()


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def current_user(authorization: str = Header(default="")):
    if not authorization.lower().startswith("bearer ") or not authorization[7:].strip():
        raise HTTPException(401, "missing bearer token")
    return authorization[7:].strip()


def ledger_of(user):
    return LEDGERS.setdefault(user, Ledger())


def visited_stops(user):
    return set(VISITS.get(user, {}))


class CheckinRequest(BaseModel):
    stop_id: str
    lat: float
    lon: float
    client_time: datetime
    mode: str | None = None
    consent: bool = True  # demo stand-in for the consent table


class FriendRequest(BaseModel):
    username: str


class RedeemRequest(BaseModel):
    offer_id: str


class VerifyRequest(BaseModel):
    code: str
    store_id: str


def redemption_json(r):
    return {"code": r.code, "offer_id": r.offer_id, "status": r.status,
            "expires_at": r.expires_at.isoformat()}


@app.post("/checkins", status_code=201)
def post_checkin(body: CheckinRequest, user: str = Depends(current_user)):
    stop = STOPS.get(body.stop_id)
    if stop is None:
        raise HTTPException(404, "unknown stop")
    t = now()
    history = VISITS.setdefault(user, {}).setdefault(body.stop_id, [])
    last = history[-1] if history else None
    res = validate_checkin(
        consent=body.consent, user_lat=body.lat, user_lon=body.lon,
        stop_lat=stop["lat"], stop_lon=stop["lon"], now=t,
        last_vehicle_seen_at=t if VEHICLE_ALWAYS_SEEN else None,
        last_checkin_at=last)
    if not res.ok:
        if not history:
            VISITS[user].pop(body.stop_id, None)
        raise HTTPException(res.http_status, res.reason)

    first = not history
    day_start = t.replace(hour=0, minute=0, second=0, microsecond=0)
    repeats_today = sum(1 for x in history if x >= day_start)
    led = ledger_of(user)
    today_pts = sum(e.delta for e in led.entries
                    if e.at >= day_start and e.reason in ("first_visit", "repeat_visit"))
    pts = checkin_points(first_visit=first, repeats_today_at_stop=repeats_today,
                         checkin_points_today=today_pts)
    old_rank = rank_for(led.lifetime)[0]
    history.append(t)
    if pts:
        led.add(t, pts, "first_visit" if first else "repeat_visit")

    extra = 0
    owned = BADGES.setdefault(user, set())
    new_rank = rank_for(led.lifetime)[0]
    new_badges = badges.unlocked_badges(visited_stops=visited_stops(user), rank=new_rank,
                                        already_have=owned)
    for q in badges.completed_quests(QUESTS, visited_stops(user), DONE_QUESTS.setdefault(user, set())):
        DONE_QUESTS[user].add(q.id)
        led.add(t, q.reward_points, "quest:" + q.id)
        extra += q.reward_points
        if q.reward_badge_id and q.reward_badge_id not in owned:
            new_badges.add(q.reward_badge_id)
    for b in new_badges:
        if b.startswith("line-"):
            led.add(t, config.COMPLETE_LINE_POINTS, "badge:" + b)
            extra += config.COMPLETE_LINE_POINTS
    owned |= new_badges
    final_rank = rank_for(led.lifetime)[0]
    return {"checkin_id": f"{user}-{len(history)}-{body.stop_id}",
            "points_awarded": pts + extra, "first_visit": first,
            "new_rank": final_rank if final_rank != old_rank else None,
            "badges_unlocked": sorted(new_badges)}


@app.get("/me/points")
def get_points(user: str = Depends(current_user)):
    led = ledger_of(user)
    recent = [{"at": e.at.isoformat(), "delta": e.delta, "reason": e.reason}
              for e in reversed(led.entries[-20:])]
    return {"balance": led.balance, "lifetime": led.lifetime, "recent": recent}


@app.get("/me/rank")
def get_rank(user: str = Depends(current_user)):
    return rank_info(ledger_of(user).lifetime)


@app.get("/me/collection")
def get_collection(user: str = Depends(current_user)):
    owned = BADGES.get(user, set())
    return {"stops": sorted(visited_stops(user)), "badges": sorted(owned),
            "physical_rewards": sorted(badges.physical_rewards_for(owned))}


@app.get("/quests")
def get_quests(user: str = Depends(current_user)):
    return [{"id": q.id, "title": q.title, "sponsor_id": q.sponsor_id,
             "goal": "Visit: " + ", ".join(sorted(q.goal_stops)),
             "reward_points": q.reward_points, "reward_badge_id": q.reward_badge_id}
            for q in QUESTS]


@app.get("/leaderboards")
def get_leaderboards(scope: str = "global", period: str = "all",
                     user: str = Depends(current_user)):
    if scope not in ("global", "friends"):
        raise HTTPException(422, "scope must be global or friends (line needs route data)")
    if period not in ("week", "month", "all"):
        raise HTTPException(422, "period must be week, month or all")
    t = now()
    scores = {u: points_in_period(l.entries, period, t) for u, l in LEDGERS.items()}
    scores.setdefault(user, 0)
    return leaderboard(scores, scope=scope, me=user, friends=FRIENDS.list(user))


@app.get("/friends")
def get_friends(user: str = Depends(current_user)):
    return [{"username": f, "rank": rank_for(ledger_of(f).lifetime)[0]} for f in FRIENDS.list(user)]


@app.post("/friends", status_code=201)
def post_friend(body: FriendRequest, user: str = Depends(current_user)):
    try:
        FRIENDS.add(user, body.username)
    except FriendError as e:
        raise HTTPException(e.http_status, e.reason)
    return {"username": body.username}


@app.post("/redemptions", status_code=201)
def post_redemption(body: RedeemRequest, user: str = Depends(current_user)):
    offer = OFFERS.get(body.offer_id)
    if offer is None:
        raise HTTPException(404, "unknown offer")
    rank = rank_for(ledger_of(user).lifetime)[0]
    try:
        red = BOOK.issue(user_id=user, store_id=offer["store_id"], offer_id=body.offer_id,
                         user_rank=rank, min_rank=offer["min_rank"], now=now())
    except RedemptionError as e:
        raise HTTPException(e.http_status, e.reason)
    return redemption_json(red)


@app.post("/redemptions/verify")
def verify_redemption(body: VerifyRequest, x_store_key: str = Header(default="")):
    if x_store_key != STORE_KEY:
        raise HTTPException(401, "bad store key")
    try:
        red = BOOK.verify(code=body.code, store_id=body.store_id, now=now())
    except RedemptionError as e:
        raise HTTPException(e.http_status, e.reason)
    return redemption_json(red)
