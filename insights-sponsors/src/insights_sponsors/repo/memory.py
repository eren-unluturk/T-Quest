import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

from ..spots import CategoryRef, Spot, SpotLabel, public_labels
from .ids import slug_to_uuid
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
PLACE_VISIT_RETENTION_DAYS = 90


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
        spots_seed = load("spots.json")
        self._categories = {c[0]: CategoryRef(slug=c[0], display_name=c[1]) for c in spots_seed["categories"]}
        self._label_names = {l[0]: l[1] for l in spots_seed["label_types"]}
        self._spot_raw = {r["id"]: r for r in spots_seed["spots"]}
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

    def _spot_sponsor_stops(self) -> dict[str, set[str]]:
        """sponsor id -> stops where that sponsor has an active nearby spot."""
        m: dict[str, set[str]] = {}
        for r in self._spot_raw.values():
            if r["active"] and r["sponsor_id"]:
                m.setdefault(r["sponsor_id"], set()).update(x["stop_id"] for x in r["stops"])
        return m

    def offers(
        self,
        stop_id: str | None = None,
        store_id: str | None = None,
        category: Category | None = None,
    ) -> list[Offer]:
        out = []
        via_spot = self._spot_sponsor_stops()
        for o in self._offers:
            store = self._stores.get(o.store_id) if o.store_id else None
            sponsor = self._sponsors.get(o.sponsor_id)
            if store_id and o.store_id != store_id:
                continue
            if stop_id:
                near_store = store is not None and store.nearest_stop_id == stop_id
                near_spot = stop_id in via_spot.get(o.sponsor_id, set())
                if not (near_store or near_spot):
                    continue
            if category:
                cat = store.category if store else (sponsor.category if sponsor else None)
                if cat != category:
                    continue
            out.append(o.model_copy(update={"demo": sponsor.demo_placeholder if sponsor else True}))
        return out

    # nearby spots
    def spot_categories(self) -> list[CategoryRef]:
        return list(self._categories.values())

    def label_types(self) -> list[dict]:
        return [{"slug": k, "display_name": v} for k, v in self._label_names.items()]

    def _build_spot(self, raw: dict, distance_m: float | None) -> Spot:
        spot = Spot(
            id=str(slug_to_uuid(raw["id"])),
            name=raw["name"],
            category=self._categories[raw["category"]],
            address=raw["address"],
            lat=raw["lat"],
            lon=raw["lon"],
            placement_type=raw["placement_type"],
            demo=raw["demo_placeholder"],
            sponsor_id=raw["sponsor_id"],
            distance_m=distance_m,
            source=raw["source"],
            offers=[],
            labels=[
                SpotLabel(
                    slug=l["label"],
                    display_name=self._label_names[l["label"]],
                    status=l["status"],
                    evidence_url=l["evidence_url"],
                    declaration_note=l["declaration_note"],
                    verified_at=l["verified_at"],
                    verified_by=l["verified_by"],
                )
                for l in raw["labels"]
            ],
        )
        spot = public_labels(spot)  # pending labels never leave the repository
        if raw["sponsor_id"]:
            spot.offers = [o for o in self.offers() if o.sponsor_id == raw["sponsor_id"]]
        return spot

    def spots_for_stop(self, stop_id: str) -> list[Spot]:
        out = []
        for raw in self._spot_raw.values():
            if not raw["active"]:
                continue
            for link in raw["stops"]:
                if link["stop_id"] == stop_id:
                    out.append(self._build_spot(raw, link["distance_m"]))
        return out

    def get_spot(self, spot_id: str) -> Spot | None:
        for raw in self._spot_raw.values():
            if str(slug_to_uuid(raw["id"])) == spot_id and raw["active"]:
                dists = [x["distance_m"] for x in raw["stops"] if x["distance_m"] is not None]
                return self._build_spot(raw, min(dists) if dists else None)
        return None

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

    def rider_events_all(self, since: datetime) -> list[RiderEvent]:
        return [e for e in self._events if e.time >= since]

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
        # 90-day retention is enforced on read: older visits are never returned.
        cutoff = datetime.now(timezone.utc) - timedelta(days=PLACE_VISIT_RETENTION_DAYS)
        floor = cutoff if since is None else max(since, cutoff)
        return [
            v for v in self._place_visits if v.user_id == user_id and v.time >= floor
        ]

    def add_place_visit(self, user_id: str, visit: PlaceVisit) -> None:
        """Callers must have checked has_consent(user, "place_visits") first."""
        self._place_visits.append(visit.model_copy(update={"user_id": user_id}))
        self._place_visits.sort(key=lambda v: v.time)

    def delete_place_visits(self, user_id: str) -> int:
        kept = [v for v in self._place_visits if v.user_id != user_id]
        deleted = len(self._place_visits) - len(kept)
        self._place_visits = kept
        return deleted

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
