from typing import Protocol

from ..models import (
    Category,
    Consent,
    ConsentScope,
    FunFact,
    Offer,
    PhysicalReward,
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

    def physical_rewards(self) -> list[PhysicalReward]: ...

    def trail_sites(self) -> list[TrailSite]: ...

    def fun_facts(self) -> list[FunFact]: ...

    def get_consents(self, user_id: str) -> list[Consent]: ...

    def set_consent(
        self, user_id: str, scope: ConsentScope, granted: bool, policy_version: str
    ) -> Consent: ...

    def user_rank(self, user_id: str) -> int: ...

    def user_badges(self, user_id: str) -> set[str]: ...
