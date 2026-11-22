"""Check-in validation. Pure functions; no database."""
import math
from dataclasses import dataclass
from datetime import timedelta

from . import config


def distance_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres (haversine)."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@dataclass
class CheckinResult:
    ok: bool
    reason: str = "ok"   # ok | no_consent | too_far | no_vehicle | cooldown | too_fast
    http_status: int = 201


def too_fast(prev, now, lat, lon):
    """True if getting from the previous check-in (at, lat, lon) to here needs more than MAX_SPEED_KMH.

    Uses server time. SPEED_SLACK_M is added so GPS jitter between nearby stops never trips it.
    """
    if prev is None:
        return False
    prev_at, prev_lat, prev_lon = prev
    seconds = max((now - prev_at).total_seconds(), 0.0)
    allowed_m = config.MAX_SPEED_KMH * 1000.0 / 3600.0 * seconds + config.SPEED_SLACK_M
    return distance_m(prev_lat, prev_lon, lat, lon) > allowed_m


def validate_checkin(*, consent, user_lat, user_lon, stop_lat, stop_lon, now,
                     last_vehicle_seen_at, last_checkin_at, previous_checkin=None):
    """Return a CheckinResult. Times are datetimes; the last_* values may be None.

    previous_checkin is (at, lat, lon) of the user's latest check-in anywhere, or None to skip the speed check.
    """
    if not consent:
        return CheckinResult(False, "no_consent", 403)
    if last_checkin_at is not None and now - last_checkin_at < timedelta(seconds=config.COOLDOWN_PER_STOP_S):
        return CheckinResult(False, "cooldown", 409)
    if distance_m(user_lat, user_lon, stop_lat, stop_lon) > config.MAX_DISTANCE_M:
        return CheckinResult(False, "too_far", 422)
    if last_vehicle_seen_at is None or now - last_vehicle_seen_at > timedelta(seconds=config.VEHICLE_SEEN_WITHIN_S):
        return CheckinResult(False, "no_vehicle", 422)
    if too_fast(previous_checkin, now, user_lat, user_lon):
        return CheckinResult(False, "too_fast", 422)
    return CheckinResult(True)
