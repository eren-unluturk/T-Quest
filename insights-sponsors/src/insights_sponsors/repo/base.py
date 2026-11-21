from datetime import datetime
from typing import Protocol

from ..spots import CategoryRef, Spot
from ..models import (
    Category,
    Consent,
    ConsentScope,
    FunFact,
    Offer,
    PhysicalReward,
    PlaceVisit,
    RiderEvent,
    Stop,
    StopFacts,
    StorePartner,
    TrailSite,
)


class Repository(Protocol):
    def get_stop(self, stop_id: str) -> Stop | None: ...

    def stop_facts(self, stop_id: str) -> StopFacts | None: ...

    def stores_near_stop(
        self, stop_id: str, limit: int
    ) -> list[tuple[StorePartner, float]]: ...

    def offers(
        self,
        stop_id: str | None = None,
        store_id: str | None = None,
        category: Category | None = None,
    ) -> list[Offer]: ...

    def spot_categories(self) -> list[CategoryRef]: ...

    def label_types(self) -> list[dict]: ...

    def spots_for_stop(self, stop_id: str) -> list[Spot]:
        """Active spots linked to the stop, with ONLY declared or certified labels."""
        ...

    def get_spot(self, spot_id: str) -> Spot | None: ...

    def stop_content(self, stop_id: str) -> list: ...

    def loading_facts(self) -> list: ...

    def physical_rewards(self) -> list[PhysicalReward]: ...

    def trail_sites(self) -> list[TrailSite]: ...

    def fun_facts(self) -> list[FunFact]: ...

    def get_consents(self, user_id: str) -> list[Consent]: ...

    def set_consent(
        self, user_id: str, scope: ConsentScope, granted: bool, policy_version: str
    ) -> Consent: ...

    def user_rank(self, user_id: str) -> int: ...

    def user_badges(self, user_id: str) -> set[str]: ...

    # reference data used by analytics and recommendations
    def stops(self) -> list[Stop]: ...

    def stores(self) -> list[StorePartner]: ...

    def route_stops(self) -> dict[str, list[str]]: ...

    # rider data
    def rider_events(
        self, user_id: str, since: datetime | None = None
    ) -> list[RiderEvent]: ...

    def rider_events_all(self, since: datetime) -> list[RiderEvent]:
        """Every rider's events since `since`. For aggregate city views only: callers
        must reduce to counts with a minimum-riders rule and never return user ids."""
        ...

    def stop_popularity(self, since: datetime) -> dict[str, int]:
        """Check-ins per stop across all riders since `since` (aggregate only)."""
        ...

    def place_visits(
        self, user_id: str, since: datetime | None = None
    ) -> list[PlaceVisit]:
        """Consent-gated: callers must pass has_consent(user, "place_visits") first."""
        ...

    def add_place_visit(self, user_id: str, visit: PlaceVisit) -> None:
        """Consent-gated: only POST /place-visits (behind require_consent) may call this."""
        ...

    def delete_place_visits(self, user_id: str) -> int:
        """Erase every stored visit for the user and return how many were deleted."""
        ...
