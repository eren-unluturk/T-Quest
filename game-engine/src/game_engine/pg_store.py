"""PgStore: the game-engine data layer on the shared Tiger Data database.

DEMO-SAFE by design:
- Read-only unless the caller passes allow_writes=True (the app sets that only
  when env GE_ALLOW_DB_WRITES=1).
- Every user the service creates is a DEMO user: the database username is
  "demo_" + the name the client sent. Every other row (points_ledger,
  user_collections, friends, redemptions) hangs off a demo user, and every
  check-in row in rider_events is written with is_synthetic = true. So
  `python -m game_engine.demo_reset` can remove all of it, and real analytics
  (which filter NOT is_synthetic) never see it.
- Only demo users are read back (leaderboards, friends), so real users are never exposed.

Tables written: users, rider_events, points_ledger, user_collections, badges
(slug rows only), friends, redemptions. Tables only read: stops, vehicles,
offers, stores, quests, spot_stop_links, nearby_spots, physical_rewards,
freedom_trail_sites, routes, route_stops. All sponsors, stores and spots in the
database are demo placeholders.

Pass a connection to PgStore(conn). With autocommit on, each statement is saved
at once. With autocommit off, nothing is saved until commit(), so tests can roll back.
"""
import hashlib
import json
import os
import secrets
from datetime import timedelta, timezone

from . import badges as badge_rules
from . import config
from .points import LedgerEntry
from .redemption import RedemptionError
from .store import encode_reason

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DEMO_PREFIX = "demo_"
NIL_UUID = "00000000-0000-0000-0000-000000000000"


class ReadOnlyStore(Exception):
    """A write was attempted while database writes are switched off."""


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

    def __init__(self, conn, allow_writes=False):
        self.conn = conn
        self.can_write = bool(allow_writes)
        self._ids = {}
        self._catalog = None
        self._catalog_at = 0

    def _w(self):
        if not self.can_write:
            raise ReadOnlyStore("database writes are off (set GE_ALLOW_DB_WRITES=1 to allow demo writes)")

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

    def vehicle_seen_at(self, stop_id, now, lat=None, lon=None):
        """Latest time a live vehicle was within VEHICLE_RADIUS_M of the stop (last 15 min).

        Matches by position, not by id: subway vehicles report platform ids
        that are not in the stops table.
        """
        if lat is None or lon is None:
            return None
        import math
        dlat = config.VEHICLE_RADIUS_M / 111000.0
        dlon = config.VEHICLE_RADIUS_M / (111000.0 * math.cos(math.radians(lat)))
        row = self._q(
            "select max(time) from vehicles where time > now() - interval '15 minutes' "
            "and lat between %s and %s and lon between %s and %s",
            (lat - dlat, lat + dlat, lon - dlon, lon + dlon), one=True)
        t = row[0] if row else None
        return _naive(t) if t else None

    def quests(self):
        """Visit-stations quests from the quests table (criteria jsonb).

        {"stops": ["place-x", ...]}                      visit every listed station
        {"stops": [...], "min_stops": 3}                  visit any 3 of them
        {"type": "spots_near_stops", "min_stops": 3}      visit any 3 stations that have a nearby spot
                                                          (stations come from spot_stop_links joined to active, not removed
                                                          nearby_spots: the same set GET /stops/{id}/nearby returns with no
                                                          filters. Read from the shared tables, no HTTP call at check-in.)
        """
        rows = self._q("select id, title, criteria, reward_points, reward_badge_id, sponsor_id "
                       "from quests where active and (starts_at is null or starts_at <= now()) "
                       "and (ends_at is null or ends_at > now())", many=True)
        out = []
        spot_stations = None
        for qid, title, criteria, pts, badge, sponsor in rows:
            criteria = criteria or {}
            stops = criteria.get("stops")
            if criteria.get("type") == "spots_near_stops":
                if spot_stations is None:
                    spot_stations = frozenset(r[0] for r in self._q(
                        "select distinct l.stop_id from spot_stop_links l join nearby_spots s on s.id = l.spot_id "
                        "where s.active and s.removed_at is null", many=True))
                stops = spot_stations
            if stops:
                out.append(badge_rules.Quest(str(qid), title, frozenset(stops), pts or 0, badge,
                                             str(sponsor) if sponsor else None,
                                             criteria.get("min_stops")))
        return out

    def physical_rewards_for(self, badge_ids):
        """Names of the stickers and patches the badges unlock (physical_rewards table)."""
        ids = list(badge_ids)
        if not ids:
            return []
        rows = self._q("select distinct name from physical_rewards where active and badge_id = any(%s) order by name",
                       (ids,), many=True)
        return [r[0] for r in rows]
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

    # users (demo users only: the database name is "demo_" + client name)
    def _uid(self, user):
        name = DEMO_PREFIX + user
        if name in self._ids:
            return self._ids[name]
        row = self._q("select id from users where username=%s", (name,), one=True)
        if row is None and self.can_write:
            self._q("insert into users (username, display_name) values (%s, %s) on conflict (username) do nothing",
                    (name, "Demo " + user))
            row = self._q("select id from users where username=%s", (name,), one=True)
        if row is None:          # read-only and unknown: matches nothing, creates nothing
            return NIL_UUID
        self._ids[name] = str(row[0])
        return self._ids[name]

    def ensure_user(self, user):
        return self._uid(user)

    # check-ins
    def checkins_at_stop(self, user, stop_id):
        rows = self._q("select time from rider_events where user_id=%s and stop_id=%s and event_type='checkin' "
                       "order by time", (self._uid(user), stop_id), many=True)
        return [_naive(r[0]) for r in rows]

    def visited_stops(self, user):
        """Visited STATIONS: a platform check-in counts for its parent station."""
        rows = self._q("select distinct coalesce(s.parent_station, s.id) from rider_events e "
                       "join stops s on s.id = e.stop_id where e.user_id=%s and e.event_type='checkin'",
                       (self._uid(user),), many=True)
        return {r[0] for r in rows}

    def catalog(self):
        """Real badge catalog from route_stops and Freedom Trail data (cached 10 min)."""
        import time
        if self._catalog and time.time() - self._catalog_at < 600:
            return self._catalog
        rows = self._q(
            "select r.line_id, r.id, array_agg(distinct coalesce(s.parent_station, s.id)) "
            "from routes r join route_stops rs on rs.route_id = r.id join stops s on s.id = rs.stop_id "
            "where r.mode in ('subway','light_rail') and r.line_id is not null group by r.line_id, r.id", many=True)
        lines = {}
        for line_id, _route_id, stations in rows:
            badge_id = "line-%s-complete" % line_id.removeprefix("line-").lower()
            lines.setdefault(badge_id, []).append(frozenset(stations))
        trail = self._q(
            "select coalesce(parent_station, id) from stops where is_freedom_trail "
            "union select coalesce(s.parent_station, s.id) from freedom_trail_sites f "
            "join stops s on s.id = f.nearest_stop_id", many=True)
        trail = frozenset(r[0] for r in trail)
        # Fewer than 2 stations means the trail data is not loaded yet: keep the badge off.
        self._catalog = badge_rules.Catalog(lines=lines, trail=trail if len(trail) >= 2 else frozenset())
        self._catalog_at = time.time()
        return self._catalog

    def record_checkin(self, user, stop_id, lat, lon, client_time, at, points, mode=None):
        self._w()
        self._q("insert into rider_events (time, user_id, event_type, stop_id, mode, lat, lon, client_time, "
                "points_awarded, is_synthetic) values (%s,%s,'checkin',%s,%s,%s,%s,%s,%s,true)",
                (at, self._uid(user), stop_id, mode, lat, lon, client_time, points))

    def last_checkin(self, user):
        """(at, lat, lon) of the user's latest check-in anywhere, or None."""
        row = self._q("select time, lat, lon from rider_events where user_id=%s and event_type='checkin' "
                      "and lat is not null and lon is not null order by time desc limit 1",
                      (self._uid(user),), one=True)
        return (_naive(row[0]), row[1], row[2]) if row else None

    # spots (placeholder places near stops, from insights-sponsors tables)
    def spot_stops(self, spot_id):
        """{station id: distance_m or None} for an active spot, or None if the spot does not exist."""
        sid = _uuid_or_none(spot_id)
        if not sid:
            return None
        rows = self._q("select l.stop_id, l.distance_m from nearby_spots s left join spot_stop_links l on l.spot_id = s.id "
                       "where s.id = %s and s.active and s.removed_at is null", (sid,), many=True)
        if not rows:
            return None
        return {r[0]: r[1] for r in rows if r[0]}

    def spot_visited_since(self, user, spot_id, since):
        row = self._q("select 1 from rider_events where user_id=%s and event_type='visit' and time >= %s "
                      "and payload->>'spot_id' = %s limit 1", (self._uid(user), since, str(spot_id)), one=True)
        return row is not None

    def record_spot_visit(self, user, spot_id, stop_id, at):
        """A rider tapped a spot: one 'visit' rider event with payload.spot_id (demo row, is_synthetic)."""
        self._w()
        self._q("insert into rider_events (time, user_id, event_type, stop_id, payload, is_synthetic) "
                "values (%s,%s,'visit',%s,%s::jsonb,true)",
                (at, self._uid(user), stop_id, json.dumps({"spot_id": str(spot_id)})))

    # points
    def ledger_entries(self, user):
        rows = self._q("select at, delta, reason, ref_type, ref_id from points_ledger where user_id=%s order by at",
                       (self._uid(user),), many=True)
        return tuple(LedgerEntry(_naive(r[0]), r[1], _decode_reason(r[2], r[3], r[4])) for r in rows)

    def add_points(self, user, at, delta, reason, ref_type=None, ref_id=None):
        self._w()
        self._q("insert into points_ledger (at, user_id, delta, reason, ref_type, ref_id) values (%s,%s,%s,%s,%s,%s)",
                (at, self._uid(user), delta, reason, ref_type, ref_id))

    def all_ledgers(self):
        """Ledgers of DEMO users only (real users are never exposed), keyed by the client name."""
        rows = self._q("select u.username, l.at, l.delta, l.reason, l.ref_type, l.ref_id "
                       "from points_ledger l join users u on u.id = l.user_id "
                       "where starts_with(u.username, %s) order by l.at", (DEMO_PREFIX,), many=True)
        out = {}
        for name, at, delta, reason, rt, rid in rows:
            out.setdefault(name.removeprefix(DEMO_PREFIX), []).append(
                LedgerEntry(_naive(at), delta, _decode_reason(reason, rt, rid)))
        return {k: tuple(v) for k, v in out.items()}

    # badges
    def badges(self, user):
        rows = self._q("select badge_id from user_collections where user_id=%s", (self._uid(user),), many=True)
        return {r[0] for r in rows}

    def add_badge(self, user, badge_id, at, source):
        self._w()
        self._q("insert into badges (id, name, kind) values (%s,%s,%s) on conflict (id) do nothing",
                (badge_id, badge_id, _badge_kind(badge_id)))
        self._q("insert into user_collections (user_id, badge_id, earned_at, source) values (%s,%s,%s,%s) "
                "on conflict (user_id, badge_id) do nothing", (self._uid(user), badge_id, at, source))

    # friends
    def add_friend(self, user, other):
        if user == other:
            return "self"
        self._w()
        a, b = self._uid(user), self._uid(other)
        row = self._q("select 1 from friends where user_id=%s and friend_id=%s", (a, b), one=True)
        if row:
            return "exists"
        self._q("insert into friends (user_id, friend_id) values (%s,%s),(%s,%s) on conflict do nothing", (a, b, b, a))
        return "ok"

    def friends(self, user):
        rows = self._q("select u.username from friends f join users u on u.id=f.friend_id where f.user_id=%s "
                       "order by u.username", (self._uid(user),), many=True)
        return [r[0].removeprefix(DEMO_PREFIX) for r in rows]

    # redemptions
    def issue_redemption(self, *, user, offer_id, offer, user_rank, balance, now):
        self._w()
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
        self._w()
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
