import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

from ..models import (
    Category,
    Consent,
    ConsentScope,
    Fact,
    FunFact,
    Offer,
    PhysicalReward,
    PlaceVisit,
    RiderEvent,
    Sponsor,
    Stop,
    StopFacts,
    StorePartner,
    TrailSite,
)

DEFAULT_SEED_DIR = Path(__file__).resolve().parents[3] / "data" / "seed"
EARTH_RADIUS_M = 6371000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = radians(lat1), radians(lat2)
    dphi = p2 - p1
    dlam = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


class MemoryRepository:
    def __init__(
        self, seed_dir: Path | str | None = None, now: datetime | None = None
    ):
        d = Path(seed_dir) if seed_dir else DEFAULT_SEED_DIR
        # Seed events store days_ago + hour so the demo data never goes stale.
        today = (now or datetime.now(timezone.utc)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        def at(rec: dict) -> datetime:
            return today - timedelta(days=rec["days_ago"]) + timedelta(hours=rec["hour"])

        def load(name: str):
            return json.loads((d / name).read_text(encoding="utf-8"))

        self._stops = {s["id"]: Stop(**s) for s in load("stops.json")}
        self._facts = {
            stop_id: [Fact(**f) for f in facts]
            for stop_id, facts in load("stop_facts.json").items()
        }
        self._trail = sorted(
            (TrailSite(**t) for t in load("freedom_trail.json")), key=lambda t: t.order
        )
        self._fun_facts = [FunFact(**f) for f in load("fun_facts.json")]
        self._sponsors = {s["id"]: Sponsor(**s) for s in load("sponsors.json")}
        self._stores = {s["id"]: StorePartner(**s) for s in load("stores.json")}
        self._offers = [Offer(**o) for o in load("offers.json")]
        self._rewards = [PhysicalReward(**r) for r in load("physical_rewards.json")]
        self._route_stops = load("route_stops.json")
        self._events = sorted(
            (
                RiderEvent(
                    time=at(e),
                    user_id=e["user_id"],
                    event_type=e["event_type"],
                    stop_id=e.get("stop_id"),
                    route_id=e.get("route_id"),
                    mode=e.get("mode"),
                )
                for e in load("rider_events.json")
            ),
            key=lambda e: e.time,
        )
        self._place_visits = sorted(
            (
                PlaceVisit(
                    time=at(v),
                    user_id=v["user_id"],
                    lat=v["lat"],
                    lon=v["lon"],
                    place_category=v["place_category"],
                    store_id=v.get("store_id"),
                )
                for v in load("place_visits.json")
            ),
            key=lambda v: v.time,
        )
        self._consents: dict[tuple[str, str], Consent] = {}
        self._profiles: dict[str, tuple[int, set[str]]] = {}

    # content
    def get_stop(self, stop_id: str) -> Stop | None:
        return self._stops.get(stop_id)

    def stop_facts(self, stop_id: str) -> StopFacts | None:
        stop = self._stops.get(stop_id)
        if stop is None:
            return None
        return StopFacts(
            stop_id=stop.id,
            stop_name=stop.name,
            facts=list(self._facts.get(stop_id, [])),
        )

    def stores_near_stop(
        self, stop_id: str, limit: int
    ) -> list[tuple[StorePartner, float]]:
        stop = self._stops.get(stop_id)
        if stop is None:
            return []
        pairs = [
            (s, haversine_m(stop.lat, stop.lon, s.lat, s.lon))
            for s in self._stores.values()
        ]
        pairs.sort(key=lambda p: p[1])
        return pairs[:limit]

    def offers(
        self,
        stop_id: str | None = None,
        store_id: str | None = None,
        category: Category | None = None,
    ) -> list[Offer]:
        out = []
        for o in self._offers:
            store = self._stores.get(o.store_id)
            if store_id and o.store_id != store_id:
                continue
            if stop_id and (store is None or store.nearest_stop_id != stop_id):
                continue
            if category and (store is None or store.category != category):
                continue
            out.append(o)
        return out

    def physical_rewards(self) -> list[PhysicalReward]:
        return list(self._rewards)

    def trail_sites(self) -> list[TrailSite]:
        return list(self._trail)

    def fun_facts(self) -> list[FunFact]:
        return list(self._fun_facts)

    def sponsors(self) -> list[Sponsor]:
        return list(self._sponsors.values())

    def stores(self) -> list[StorePartner]:
        return list(self._stores.values())

    def stops(self) -> list[Stop]:
        return list(self._stops.values())

    def route_stops(self) -> dict[str, list[str]]:
        return {r: list(s) for r, s in self._route_stops.items()}

    # rider data
    def rider_events(
        self, user_id: str, since: datetime | None = None
    ) -> list[RiderEvent]:
        return [
            e
            for e in self._events
            if e.user_id == user_id and (since is None or e.time >= since)
        ]

    def stop_popularity(self, since: datetime) -> dict[str, int]:
        counts = Counter(
            e.stop_id
            for e in self._events
            if e.event_type == "checkin" and e.stop_id and e.time >= since
        )
        return dict(counts)

    def place_visits(
        self, user_id: str, since: datetime | None = None
    ) -> list[PlaceVisit]:
        return [
            v
            for v in self._place_visits
            if v.user_id == user_id and (since is None or v.time >= since)
        ]

    # consent
    def get_consents(self, user_id: str) -> list[Consent]:
        return [c for (uid, _), c in self._consents.items() if uid == user_id]

    def set_consent(
        self, user_id: str, scope: ConsentScope, granted: bool, policy_version: str
    ) -> Consent:
        now = datetime.now(timezone.utc)
        prev = self._consents.get((user_id, scope))
        if granted:
            rec = Consent(
                scope=scope,
                granted=True,
                granted_at=now,
                revoked_at=None,
                policy_version=policy_version,
            )
        else:
            rec = Consent(
                scope=scope,
                granted=False,
                granted_at=prev.granted_at if prev else None,
                revoked_at=now,
                policy_version=policy_version,
            )
        self._consents[(user_id, scope)] = rec
        return rec

    # profile (rank and badges come from game-engine in production)
    def set_user_profile(
        self, user_id: str, rank: int = 1, badges: set[str] | None = None
    ) -> None:
        self._profiles[user_id] = (rank, set(badges or ()))

    def user_rank(self, user_id: str) -> int:
        return self._profiles.get(user_id, (1, set()))[0]

    def user_badges(self, user_id: str) -> set[str]:
        return set(self._profiles.get(user_id, (1, set()))[1])
