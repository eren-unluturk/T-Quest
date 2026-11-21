"""Personal route analytics computed from rider events.

Mirrors sql/analytics_me.sql. This in-memory version keeps the endpoint alive
until the Postgres backend reads the Tiger Data aggregates.
"""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from .models import (
    BostonAnalytics,
    BusiestStop,
    DayCount,
    LineActivity,
    MyAnalytics,
    RiderEvent,
    TopStop,
    TrendingNeighborhood,
    WeekBucket,
)
from .repo import Repository

VISIT_TYPES = {"checkin", "visit"}
PERIOD_DAYS = {"week": 7, "month": 30, "all": None}
HOME_LINE_WINDOW_DAYS = 28
HOME_LINE_MIN_CHECKINS = 5
TOP_STOPS = 5


def week_start(d: date) -> date:
    """Monday of the week, matching time_bucket('1 week', ...) in Postgres."""
    return d - timedelta(days=d.weekday())


def detect_home_line(events: list[RiderEvent], now: datetime) -> str | None:
    """Line with the most check-ins in the last 28 days, with at least 5."""
    since = now - timedelta(days=HOME_LINE_WINDOW_DAYS)
    counts = Counter(
        e.route_id
        for e in events
        if e.event_type == "checkin" and e.route_id and e.time >= since
    )
    if not counts:
        return None
    # ties broken by route id, like ORDER BY checkins DESC, route_id
    route, n = min(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return route if n >= HOME_LINE_MIN_CHECKINS else None


def compute_analytics(
    repo: Repository,
    user_id: str,
    period: str = "month",
    now: datetime | None = None,
) -> MyAnalytics:
    now = now or datetime.now(timezone.utc)
    days = PERIOD_DAYS[period]
    since = now - timedelta(days=days) if days else None

    all_events = repo.rider_events(user_id)
    events = [
        e
        for e in all_events
        if e.event_type in VISIT_TYPES
        and e.stop_id
        and (since is None or e.time >= since)
    ]

    visits = Counter(e.stop_id for e in events)
    weekly: dict[date, list[RiderEvent]] = defaultdict(list)
    for e in events:
        weekly[week_start(e.time.date())].append(e)

    neighborhoods = set()
    for stop_id in visits:
        stop = repo.get_stop(stop_id)
        if stop and stop.neighborhood:
            neighborhoods.add(stop.neighborhood)

    top = sorted(visits.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_STOPS]
    return MyAnalytics(
        user_id=user_id,
        period=period,
        stops_visited=len(events),
        unique_stops=len(visits),
        lines_ridden=sorted({e.route_id for e in events if e.route_id}),
        home_line=detect_home_line(all_events, now),
        by_week=[
            WeekBucket(
                week_start=ws,
                checkins=len(evs),
                unique_stops=len({e.stop_id for e in evs}),
            )
            for ws, evs in sorted(weekly.items())
        ],
        top_stops=[TopStop(stop_id=s, visits=n) for s, n in top],
        neighborhoods_explored=sorted(neighborhoods),
    )


# ---- city-wide view (GET /analytics/boston), aggregate only
MIN_USERS = 3  # k-anonymity: a bucket needs at least this many distinct riders
MIN_NEIGHBORHOOD_CHECKINS = 5
BUSIEST_STOPS = 10
TRENDING_NEIGHBORHOODS = 5
CITY_PERIOD_DAYS = {"week": 7, "month": 30}


def _tally(events: list[RiderEvent], key) -> dict:
    """key(event) -> [check-ins, set of riders]. The rider sets never leave this module."""
    out: dict = defaultdict(lambda: [0, set()])
    for e in events:
        k = key(e)
        if k is None:
            continue
        out[k][0] += 1
        out[k][1].add(e.user_id)
    return out


def boston_analytics(
    repo: Repository, period: str = "week", now: datetime | None = None
) -> BostonAnalytics:
    """Anonymous city view. Any bucket backed by fewer than 3 distinct riders is
    left out, and no user id is ever returned. Mirrors sql/analytics_boston.sql."""
    now = now or datetime.now(timezone.utc)
    days = CITY_PERIOD_DAYS[period]
    cur_since = now - timedelta(days=days)
    prev_since = now - timedelta(days=2 * days)

    checkins = [
        e
        for e in repo.rider_events_all(prev_since)
        if e.event_type == "checkin" and e.stop_id
    ]
    current = [e for e in checkins if e.time >= cur_since]
    previous = [e for e in checkins if e.time < cur_since]

    riders = {e.user_id for e in current}
    enough = len(riders) >= MIN_USERS

    # busiest stops
    by_stop = _tally(current, lambda e: e.stop_id)
    busiest = sorted(
        ((s, c) for s, (c, users) in by_stop.items() if len(users) >= MIN_USERS),
        key=lambda kv: (-kv[1], kv[0]),
    )[:BUSIEST_STOPS]
    busiest_stops = []
    for stop_id, n in busiest:
        stop = repo.get_stop(stop_id)
        busiest_stops.append(
            BusiestStop(stop_id=stop_id, stop_name=stop.name if stop else stop_id, checkins=n)
        )

    # trending neighborhoods: this period vs the previous period of equal length
    def hood(e: RiderEvent) -> str | None:
        stop = repo.get_stop(e.stop_id)
        return stop.neighborhood if stop and stop.neighborhood else None

    cur_h = _tally(current, hood)
    prev_h = _tally(previous, hood)
    trending = []
    for name, (n, users) in cur_h.items():
        if n < MIN_NEIGHBORHOOD_CHECKINS or len(users) < MIN_USERS:
            continue
        pn, pusers = prev_h.get(name, [0, set()])
        # a previous period that is itself below the rider threshold counts as no data
        base = pn if len(pusers) >= MIN_USERS else 0
        change = 100.0 if base == 0 else round((n - base) / base * 100, 1)
        trending.append(TrendingNeighborhood(neighborhood=name, checkins=n, change_pct=change))
    trending.sort(key=lambda t: (-t.change_pct, -t.checkins, t.neighborhood))

    # lines, with a per-day series; days or lines under the threshold are omitted
    lines = []
    by_line = _tally([e for e in current if e.route_id], lambda e: e.route_id)
    for route_id, (n, users) in sorted(by_line.items()):
        if len(users) < MIN_USERS:
            continue
        daily = _tally([e for e in current if e.route_id == route_id], lambda e: e.time.date())
        lines.append(
            LineActivity(
                route_id=route_id,
                checkins=n,
                by_day=[
                    DayCount(day=d, checkins=c)
                    for d, (c, u) in sorted(daily.items())
                    if len(u) >= MIN_USERS
                ],
            )
        )

    return BostonAnalytics(
        period=period,
        generated_at=now,
        total_checkins=len(current) if enough else 0,
        active_riders=len(riders) if enough else 0,
        busiest_stops=busiest_stops,
        trending_neighborhoods=trending[:TRENDING_NEIGHBORHOODS],
        lines=lines,
    )
