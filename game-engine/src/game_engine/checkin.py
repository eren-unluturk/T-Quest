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
    reason: str = "ok"   # ok | no_consent | too_far | no_vehicle | cooldown
    http_status: int = 201


def validate_checkin(*, consent, user_lat, user_lon, stop_lat, stop_lon, now,
                     last_vehicle_seen_at, last_checkin_at):
    """Return a CheckinResult. Times are datetimes; the last_* values may be None."""
    if not consent:
        return CheckinResult(False, "no_consent", 403)
    if last_checkin_at is not None and now - last_checkin_at < timedelta(seconds=config.COOLDOWN_PER_STOP_S):
        return CheckinResult(False, "cooldown", 409)
    if distance_m(user_lat, user_lon, stop_lat, stop_lon) > config.MAX_DISTANCE_M:
        return CheckinResult(False, "too_far", 422)
    if last_vehicle_seen_at is None or now - last_vehicle_seen_at > timedelta(seconds=config.VEHICLE_SEEN_WITHIN_S):
        return CheckinResult(False, "no_vehicle", 422)
    return CheckinResult(True)
