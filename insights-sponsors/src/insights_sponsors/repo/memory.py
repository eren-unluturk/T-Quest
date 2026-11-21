import json
from datetime import datetime, timezone
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
    def __init__(self, seed_dir: Path | str | None = None):
        d = Path(seed_dir) if seed_dir else DEFAULT_SEED_DIR

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
