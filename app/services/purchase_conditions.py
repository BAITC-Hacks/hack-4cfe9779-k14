"""A replaceable, reviewable source for purchase conditions."""

from typing import Protocol

from app.config.purchase_conditions import UNAVAILABLE_PURCHASE_CONDITIONS
from app.schemas.purchase_conditions import PurchaseConditions


class PurchaseConditionsProvider(Protocol):
    def get_conditions(self) -> PurchaseConditions: ...


class UnavailablePurchaseConditionsProvider:
    """Returns no purchase facts until an approved provider is configured."""

    def get_conditions(self) -> PurchaseConditions:
        return UNAVAILABLE_PURCHASE_CONDITIONS.model_copy(deep=True)
