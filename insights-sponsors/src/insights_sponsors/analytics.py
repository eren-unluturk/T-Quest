"""Personal route analytics computed from rider events.

Mirrors sql/analytics_me.sql. This in-memory version keeps the endpoint alive
until the Postgres backend reads the Tiger Data aggregates.
"""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from .models import MyAnalytics, RiderEvent, TopStop, WeekBucket
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
