"""PgStore: the game-engine data layer on the shared Tiger Data database.

Tables written (owned by game-engine per contracts/db/SCHEMA.md): users,
rider_events, points_ledger, user_collections, badges, friends, redemptions.
Tables only read: stops, vehicles, offers, stores, quests.

Pass a connection to PgStore(conn). With autocommit on, each statement is saved
at once (production). With autocommit off, nothing is saved until commit(), so
tests can roll back.
"""
import hashlib
import os
import secrets
from datetime import timedelta, timezone

from . import badges as badge_rules
from . import config
from .points import LedgerEntry
from .redemption import RedemptionError
from .store import encode_reason

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _naive(dt):
    """Timezone-aware datetime -> naive UTC (the service works in naive UTC)."""
    if dt is None or dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _decode_reason(reason, ref_type, ref_id):
    if ref_type in ("quest", "badge") and ref_id:
        return f"{reason}:{ref_id}"
    return reason


def _badge_kind(badge_id):
    if badge_id.startswith("line-"):
        return "line_complete"
    if badge_id.startswith("rank-"):
        return "rank"
    if badge_id == "freedom-trail":
        return "trail"
    return "event"


def _uuid_or_none(value):
    import uuid
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError):
        return None


def connect(url=None):
    import psycopg
    url = url or os.environ["DATABASE_URL"]
    conn = psycopg.connect(url, autocommit=True, connect_timeout=15)
    conn.execute("set timezone = 'UTC'")
    return conn


class PgStore:
    name = "postgres"

    def __init__(self, conn):
        self.conn = conn
        self._ids = {}

    def _q(self, sql, params=(), one=False, many=False):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            if one:
                return cur.fetchone()
            if many:
                return cur.fetchall()
        return None

    # reference data
    def stop(self, stop_id):
        row = self._q("select lat, lon, coalesce(mode,'subway') from stops where id=%s", (stop_id,), one=True)
        return {"lat": row[0], "lon": row[1], "mode": row[2]} if row else None

    def vehicle_seen_at(self, stop_id, now):
        row = self._q(
            "select max(time) from vehicles where time > now() - interval '1 hour' "
            "and (stop_id = %s or stop_id in (select id from stops where parent_station = %s))",
            (stop_id, stop_id), one=True)
        t = row[0] if row else None
        return _naive(t) if t else None

    def quests(self):
        """Visit-these-stops quests. criteria jsonb: {"stops": ["id", ...]}."""
        rows = self._q("select id, title, criteria, reward_points, reward_badge_id, sponsor_id "
                       "from quests where active", many=True)
        out = []
        for qid, title, criteria, pts, badge, sponsor in rows:
            stops = (criteria or {}).get("stops")
            if stops:
                out.append(badge_rules.Quest(str(qid), title, frozenset(stops), pts or 0, badge,
                                             str(sponsor) if sponsor else None))
        return out

    def offer(self, offer_id):
        oid = _uuid_or_none(offer_id)
        if not oid:
            return None
        row = self._q("select id, store_id, title, min_rank, points_cost, stock, active, starts_at, ends_at "
                      "from offers where id=%s", (oid,), one=True)
        if not row or not row[6]:
            return None
        return {"id": str(row[0]), "store_id": str(row[1]) if row[1] else None, "title": row[2],
                "min_rank": row[3] or 1, "points_cost": row[4] or 0, "stock": row[5],
                "starts_at": row[7], "ends_at": row[8]}

    # users
    def ensure_user(self, user):
        if user in self._ids:
            return self._ids[user]
        self._q("insert into users (username) values (%s) on conflict (username) do nothing", (user,))
        row = self._q("select id from users where username=%s", (user,), one=True)
        self._ids[user] = str(row[0])
        return self._ids[user]

    def _uid(self, user):
        return self.ensure_user(user)

    # check-ins
    def checkins_at_stop(self, user, stop_id):
        rows = self._q("select time from rider_events where user_id=%s and stop_id=%s and event_type='checkin' "
                       "and not is_synthetic order by time", (self._uid(user), stop_id), many=True)
        return [_naive(r[0]) for r in rows]

    def visited_stops(self, user):
        rows = self._q("select distinct stop_id from rider_events where user_id=%s and event_type='checkin' "
                       "and not is_synthetic and stop_id is not null", (self._uid(user),), many=True)
        return {r[0] for r in rows}

    def record_checkin(self, user, stop_id, lat, lon, client_time, at, points, mode=None):
        self._q("insert into rider_events (time, user_id, event_type, stop_id, mode, lat, lon, client_time, "
                "points_awarded) values (%s,%s,'checkin',%s,%s,%s,%s,%s,%s)",
                (at, self._uid(user), stop_id, mode, lat, lon, client_time, points))

    # points
    def ledger_entries(self, user):
        rows = self._q("select at, delta, reason, ref_type, ref_id from points_ledger where user_id=%s order by at",
                       (self._uid(user),), many=True)
        return tuple(LedgerEntry(_naive(r[0]), r[1], _decode_reason(r[2], r[3], r[4])) for r in rows)

    def add_points(self, user, at, delta, reason, ref_type=None, ref_id=None):
        self._q("insert into points_ledger (at, user_id, delta, reason, ref_type, ref_id) values (%s,%s,%s,%s,%s,%s)",
                (at, self._uid(user), delta, reason, ref_type, ref_id))

    def all_ledgers(self):
        rows = self._q("select u.username, l.at, l.delta, l.reason, l.ref_type, l.ref_id "
                       "from points_ledger l join users u on u.id = l.user_id order by l.at", many=True)
        out = {}
        for name, at, delta, reason, rt, rid in rows:
            out.setdefault(name, []).append(LedgerEntry(_naive(at), delta, _decode_reason(reason, rt, rid)))
        return {k: tuple(v) for k, v in out.items()}

    # badges
    def badges(self, user):
        rows = self._q("select badge_id from user_collections where user_id=%s", (self._uid(user),), many=True)
        return {r[0] for r in rows}

    def add_badge(self, user, badge_id, at, source):
        self._q("insert into badges (id, name, kind) values (%s,%s,%s) on conflict (id) do nothing",
                (badge_id, badge_id, _badge_kind(badge_id)))
        self._q("insert into user_collections (user_id, badge_id, earned_at, source) values (%s,%s,%s,%s) "
                "on conflict (user_id, badge_id) do nothing", (self._uid(user), badge_id, at, source))

    # friends
    def add_friend(self, user, other):
        if user == other:
            return "self"
        a, b = self._uid(user), self._uid(other)
        row = self._q("select 1 from friends where user_id=%s and friend_id=%s", (a, b), one=True)
        if row:
            return "exists"
        self._q("insert into friends (user_id, friend_id) values (%s,%s),(%s,%s) on conflict do nothing", (a, b, b, a))
        return "ok"

    def friends(self, user):
        rows = self._q("select u.username from friends f join users u on u.id=f.friend_id where f.user_id=%s "
                       "order by u.username", (self._uid(user),), many=True)
        return [r[0] for r in rows]

    # redemptions
    def issue_redemption(self, *, user, offer_id, offer, user_rank, balance, now):
        uid = self._uid(user)
        if user_rank < offer["min_rank"]:
            raise RedemptionError("rank_too_low", 403)
        if offer["starts_at"] and now < _naive(offer["starts_at"]):
            raise RedemptionError("not_started", 409)
        if offer["ends_at"] and now > _naive(offer["ends_at"]):
            raise RedemptionError("ended", 409)
        week_ago = now - timedelta(days=7)
        if offer["store_id"]:
            row = self._q("select 1 from redemptions where user_id=%s and store_id=%s and issued_at > %s limit 1",
                          (uid, offer["store_id"], week_ago), one=True)
        else:
            row = self._q("select 1 from redemptions where user_id=%s and offer_id=%s and issued_at > %s limit 1",
                          (uid, offer["id"], week_ago), one=True)
        if row:
            raise RedemptionError("weekly_store_limit", 409)
        if offer["stock"] is not None:
            used = self._q("select count(*) from redemptions where offer_id=%s and status in ('issued','claimed')",
                           (offer["id"],), one=True)[0]
            if used >= offer["stock"]:
                raise RedemptionError("out_of_stock", 409)
        cost = offer["points_cost"]
        if cost and balance < cost:
            raise RedemptionError("not_enough_points", 409)
        expires = now + timedelta(hours=config.CODE_TTL_HOURS)
        for _ in range(5):
            code = "".join(secrets.choice(_ALPHABET) for _ in range(10))
            row = self._q("insert into redemptions (code, user_id, store_id, offer_id, status, points_spent, "
                          "issued_at, expires_at) values (%s,%s,%s,%s,'issued',%s,%s,%s) "
                          "on conflict (code) do nothing returning id", 
                          (code, uid, offer["store_id"], offer["id"], cost, now, expires), one=True)
            if row:
                if cost:
                    self.add_points(user, now, -cost, "redemption", "offer", offer["id"])
                return {"code": code, "offer_id": offer["id"], "status": "issued",
                        "expires_at": expires, "points_spent": cost}
        raise RedemptionError("try_again", 503)

    def verify_redemption(self, *, code, store_id, store_key, now):
        sid = _uuid_or_none(store_id)
        row = self._q("select id, store_id, offer_id, status, expires_at from redemptions where code=%s",
                      (code,), one=True)
        if row is None or sid is None:
            raise RedemptionError("unknown_code", 404)
        rid, rstore, offer_id, status, expires = row
        if rstore is not None and str(rstore) != sid:
            raise RedemptionError("unknown_code", 404)
        if status == "claimed":
            raise RedemptionError("already_used", 410)
        if now > _naive(expires):
            self._q("update redemptions set status='expired' where id=%s", (rid,))
            raise RedemptionError("expired", 410)
        self._q("update redemptions set status='claimed', claimed_at=%s, claimed_store_id=%s where id=%s",
                (now, sid, rid))
        return {"code": code, "offer_id": str(offer_id) if offer_id else None, "status": "claimed",
                "expires_at": _naive(expires)}

    def store_key_ok(self, store_id, store_key):
        """True if the key matches the store's stored sha256 hash (hex)."""
        sid = _uuid_or_none(store_id)
        if not sid or not store_key:
            return False
        row = self._q("select store_key_hash from stores where id=%s and active", (sid,), one=True)
        if not row or not row[0]:
            return False
        return secrets.compare_digest(hashlib.sha256(store_key.encode()).hexdigest(), row[0].lower())
