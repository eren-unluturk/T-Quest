"""Points rules and an append-only ledger (in memory for now)."""
from dataclasses import dataclass, field
from datetime import datetime

from . import config


def checkin_points(*, first_visit, repeats_today_at_stop, checkin_points_today):
    """Points for one valid check-in, honouring the daily cap."""
    if first_visit:
        base = config.FIRST_VISIT_POINTS
    elif repeats_today_at_stop < config.REPEAT_VISITS_PER_STOP_PER_DAY:
        base = config.REPEAT_VISIT_POINTS
    else:
        base = 0
    room = max(0, config.DAILY_CHECKIN_POINTS_CAP - checkin_points_today)
    return min(base, room)


@dataclass(frozen=True)
class LedgerEntry:
    at: datetime
    delta: int
    reason: str


@dataclass
class Ledger:
    """Append-only: entries can be added, never changed or removed."""
    _entries: list = field(default_factory=list)

    def add(self, at, delta, reason):
        entry = LedgerEntry(at, int(delta), reason)
        self._entries.append(entry)
        return entry

    @property
    def entries(self):
        return tuple(self._entries)

    @property
    def balance(self):
        return sum(e.delta for e in self._entries)

    @property
    def lifetime(self):
        return sum(e.delta for e in self._entries if e.delta > 0)
