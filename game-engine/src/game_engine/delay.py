"""Home line and delay compensation rules. Pure functions; no database."""
from collections import Counter
from datetime import timedelta

from . import config

HOME_LINE_WINDOW_DAYS = 30
HOME_LINE_MIN_RIDES = 5

# MBTA alert effects that count as an outage (plus the older generic names)
OUTAGE_EFFECTS = frozenset({"NO_SERVICE", "SUSPENSION", "SHUTTLE", "SIGNIFICANT_DELAY",
                            "OUTAGE", "CANCELLATION"})


def home_line(rides, now):
    """rides: iterable of (at, line_id). Most-ridden line in the last 30 days.

    Needs at least HOME_LINE_MIN_RIDES rides on that line. Ties go to the line
    ridden most recently. Returns a line id or None.
    """
    cutoff = now - timedelta(days=HOME_LINE_WINDOW_DAYS)
    recent = [(at, line) for at, line in rides if at > cutoff]
    if not recent:
        return None
    counts = Counter(line for _, line in recent)
    latest = {}
    for at, line in recent:
        if line not in latest or at > latest[line]:
            latest[line] = at
    best = max(counts, key=lambda ln: (counts[ln], latest[ln]))
    return best if counts[best] >= HOME_LINE_MIN_RIDES else None


def compensation_points(*, alert_id, alert_line, alert_effect, user_home_line, already_paid_alerts):
    """Points owed for one alert. Only outages, only home-line users, once per alert."""
    if (alert_effect or "").upper() not in OUTAGE_EFFECTS:
        return 0
    if user_home_line is None or user_home_line != alert_line:
        return 0
    if alert_id in already_paid_alerts:
        return 0
    return config.DELAY_COMPENSATION_POINTS
