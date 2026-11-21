"""Recommendations computed with the same logic as the files in sql/.

Signals:
- unvisited neighborhoods that are popular and reachable on lines the user rides
  (sql/recs_unvisited_neighborhoods.sql), score 1 / popularity rank
- unridden routes that connect to the home line (sql/recs_routes.sql),
  score 0.8 * shared stops / max shared stops
- stops near store categories the user visited (sql/recs_place_affinity.sql),
  score 0.6 * category share. Read only after has_consent(user, "place_visits").

Sponsorship never changes ordering: items are ranked organically first, then
flagged `sponsored` when an active sponsored_quest offer sits at a store near
the recommended stop(s).
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .analytics import VISIT_TYPES, detect_home_line
from .consent import has_consent
from .models import Recommendation, Recommendations
from .repo import Repository

POPULARITY_DAYS = 30
PLACE_VISIT_DAYS = 90
ROUTE_WEIGHT = 0.8
PLACE_WEIGHT = 0.6


@dataclass
class _Candidate:
    kind: str
    id: str
    title: str
    reason: str
    score: float
    stop_ids: set[str] = field(default_factory=set)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _neighborhood_candidates(repo, ridden, visited_hoods, now) -> list[_Candidate]:
    stops = {s.id: s for s in repo.stops()}
    route_stops = repo.route_stops()
    via: dict[str, set[str]] = {}
    for route in ridden:
        for stop_id in route_stops.get(route, []):
            stop = stops.get(stop_id)
            if stop and stop.neighborhood:
                via.setdefault(stop.neighborhood, set()).add(route)

    popularity: Counter = Counter()
    for stop_id, n in repo.stop_popularity(now - timedelta(days=POPULARITY_DAYS)).items():
        stop = stops.get(stop_id)
        if stop and stop.neighborhood:
            popularity[stop.neighborhood] += n

    ranked = sorted(
        (
            (hood, n)
            for hood, n in popularity.items()
            if n > 0 and hood in via and hood not in visited_hoods
        ),
        key=lambda kv: (-kv[1], kv[0]),
    )
    out = []
    for rank, (hood, n) in enumerate(ranked, 1):
        lines = ", ".join(sorted(via[hood]))
        out.append(
            _Candidate(
                kind="neighborhood",
                id=f"neighborhood.{_slug(hood)}",
                title=f"Explore {hood}",
                reason=(
                    f"{n} check-ins there in the last {POPULARITY_DAYS} days, "
                    f"and you can get there on the {lines} line you ride"
                ),
                score=1.0 / rank,
                stop_ids={s.id for s in stops.values() if s.neighborhood == hood},
            )
        )
    return out


def _route_candidates(repo, ridden, home_line) -> list[_Candidate]:
    if home_line is None:
        return []
    route_stops = repo.route_stops()
    home_stops = set(route_stops.get(home_line, []))
    shared = {
        route: len(home_stops & set(stop_ids))
        for route, stop_ids in route_stops.items()
        if route not in ridden
    }
    shared = {r: n for r, n in shared.items() if n > 0}
    if not shared:
        return []
    top = max(shared.values())
    return [
        _Candidate(
            kind="route",
            id=route,
            title=f"Ride the {route} Line",
            reason=f"Connects to your home line ({home_line}) at {n} shared stop(s)",
            score=ROUTE_WEIGHT * n / top,
            stop_ids=set(route_stops[route]),
        )
        for route, n in sorted(shared.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _place_affinity_candidates(repo, user_id, visited_stops, now) -> list[_Candidate]:
    """The only reader of place_visits. Gated on consent, checked right here."""
    if not has_consent(repo, user_id, "place_visits"):
        return []
    since = now - timedelta(days=PLACE_VISIT_DAYS)
    counts = Counter(v.place_category for v in repo.place_visits(user_id, since))
    total = sum(counts.values())
    if not total:
        return []
    share = {cat: n / total for cat, n in counts.items()}

    best: dict[str, float] = {}
    for store in repo.stores():
        if store.category in share and store.nearest_stop_id not in visited_stops:
            best[store.nearest_stop_id] = max(
                best.get(store.nearest_stop_id, 0.0), share[store.category]
            )
    names = {s.id: s.name for s in repo.stops()}
    liked = ", ".join(sorted(share))
    return [
        _Candidate(
            kind="stop",
            id=stop_id,
            title=f"Try {names.get(stop_id, stop_id)}",
            reason=f"Near places you like ({liked})",
            score=PLACE_WEIGHT * s,
            stop_ids={stop_id},
        )
        for stop_id, s in sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _sponsored_stops(repo, now) -> dict[str, str]:
    """stop_id -> sponsor_id for stops with an active sponsored_quest offer nearby."""
    store_stop = {s.id: s.nearest_stop_id for s in repo.stores()}
    out: dict[str, str] = {}
    for offer in sorted(repo.offers(), key=lambda o: o.id):
        active = offer.starts_at <= now and (offer.ends_at is None or offer.ends_at > now)
        stop_id = store_stop.get(offer.store_id)
        if offer.placement == "sponsored_quest" and active and stop_id:
            out.setdefault(stop_id, offer.sponsor_id)
    return out


def recommend(
    repo: Repository,
    user_id: str,
    kind: str | None = None,
    limit: int = 5,
    now: datetime | None = None,
) -> Recommendations:
    now = now or datetime.now(timezone.utc)
    events = repo.rider_events(user_id)
    visit_events = [e for e in events if e.event_type in VISIT_TYPES and e.stop_id]
    visited_stops = {e.stop_id for e in visit_events}
    ridden = {e.route_id for e in events if e.route_id}
    hoods = set()
    for stop_id in visited_stops:
        stop = repo.get_stop(stop_id)
        if stop and stop.neighborhood:
            hoods.add(stop.neighborhood)
    home_line = detect_home_line(events, now)

    candidates = (
        _neighborhood_candidates(repo, ridden, hoods, now)
        + _route_candidates(repo, ridden, home_line)
        + _place_affinity_candidates(repo, user_id, visited_stops, now)
    )
    # Organic ranking first. Sponsorship below only adds a flag.
    candidates.sort(key=lambda c: (-c.score, c.id))
    if kind:
        candidates = [c for c in candidates if c.kind == kind]

    sponsored = _sponsored_stops(repo, now)
    items = []
    for c in candidates[:limit]:
        sponsor_id = next(
            (sponsored[s] for s in sorted(c.stop_ids) if s in sponsored), None
        )
        items.append(
            Recommendation(
                kind=c.kind,
                id=c.id,
                title=c.title,
                reason=c.reason,
                score=round(c.score, 4),
                sponsored=sponsor_id is not None,
                sponsor_id=sponsor_id,
            )
        )
    return Recommendations(generated_at=now, items=items)
