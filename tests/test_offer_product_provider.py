from decimal import Decimal

import pytest

from app.integrations.ekt_client import EktConnectionError, EktDataUnavailableError
from app.schemas.catalog import FreshCatalogProduct
from app.services.errors import CatalogUnavailable
from app.services.offer_product_provider import CatalogCurrentProductProvider

pytestmark = pytest.mark.asyncio


class FreshCatalog:
    def __init__(self, product=None, error=None) -> None:
        self.product = product
        self.error = error
        self.calls = []

    async def get_fresh_product(self, article, *, persist=True):
        assert persist is False
        self.calls.append(article)
        if self.error is not None:
            raise self.error
        return self.product


def fresh_product(*, external_id: str | None = "source-1") -> FreshCatalogProduct:
    return FreshCatalogProduct(
        article="A-1", external_id=external_id, name="Cable", category="Cable",
        characteristics={"cores": 3}, cached_price=Decimal("10.00"),
        cached_stock_by_location={"A": 2}, cached_available=True,
        certificates=[], source_field_presence={"certificates": True},
    )


async def test_catalog_provider_uses_only_a_fresh_normalized_product() -> None:
    catalog = FreshCatalog(fresh_product())

    result = await CatalogCurrentProductProvider(catalog).get_current_product_by_article("A-1")

    assert result.id == "source-1"
    assert result.price == Decimal("10.00")
    assert result.stock_by_location == {"A": 2}
    assert catalog.calls == ["A-1"]


async def test_catalog_provider_does_not_invent_missing_source_identifier() -> None:
    catalog = FreshCatalog(fresh_product(external_id=None))

    with pytest.raises(EktDataUnavailableError):
        await CatalogCurrentProductProvider(catalog).get_current_product_by_article("A-1")


async def test_catalog_provider_normalizes_catalog_failure_before_offer_flow() -> None:
    catalog = FreshCatalog(error=CatalogUnavailable("offline"))

    with pytest.raises(EktConnectionError):
        await CatalogCurrentProductProvider(catalog).get_current_product_by_article("A-1")
