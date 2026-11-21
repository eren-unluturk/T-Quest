"""Single-use redemption codes with limits. In-memory for now."""
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import config

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


class RedemptionError(Exception):
    def __init__(self, reason, http_status):
        super().__init__(reason)
        self.reason = reason
        self.http_status = http_status


@dataclass
class Redemption:
    code: str
    user_id: str
    store_id: str
    offer_id: str
    issued_at: datetime
    expires_at: datetime
    status: str = "issued"   # issued | claimed | expired


def _new_code():
    return "".join(secrets.choice(_ALPHABET) for _ in range(10))


class RedemptionBook:
    def __init__(self, stock=None):
        self._by_code = {}
        self._stock = dict(stock or {})   # offer_id -> units left; missing = unlimited

    def issue(self, *, user_id, store_id, offer_id, user_rank, min_rank, now):
        if user_rank < min_rank:
            raise RedemptionError("rank_too_low", 403)
        week_ago = now - timedelta(days=7)
        for r in self._by_code.values():
            if r.user_id == user_id and r.store_id == store_id and r.issued_at > week_ago:
                raise RedemptionError("weekly_store_limit", 409)
        if offer_id in self._stock:
            if self._stock[offer_id] <= 0:
                raise RedemptionError("out_of_stock", 409)
            self._stock[offer_id] -= 1
        code = _new_code()
        while code in self._by_code:
            code = _new_code()
        red = Redemption(code, user_id, store_id, offer_id, now,
                         now + timedelta(hours=config.CODE_TTL_HOURS))
        self._by_code[code] = red
        return red

    def verify(self, *, code, store_id, now):
        red = self._by_code.get(code)
        if red is None or red.store_id != store_id:
            raise RedemptionError("unknown_code", 404)
        if red.status == "claimed":
            raise RedemptionError("already_used", 410)
        if now > red.expires_at:
            red.status = "expired"
            raise RedemptionError("expired", 410)
        red.status = "claimed"
        return red
