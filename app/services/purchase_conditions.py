"""A replaceable, reviewable source for purchase conditions."""

from typing import Protocol

from app.config.purchase_conditions import DEMO_PURCHASE_CONDITIONS
from app.schemas.purchase_conditions import PurchaseConditions


class PurchaseConditionsProvider(Protocol):
    def get_conditions(self) -> PurchaseConditions: ...


class DemoPurchaseConditionsProvider:
    """Explicitly non-production placeholder until approved partner terms arrive."""

    def get_conditions(self) -> PurchaseConditions:
        return DEMO_PURCHASE_CONDITIONS.model_copy(deep=True)
