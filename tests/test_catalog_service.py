from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.integrations.ekt_client import EktConnectionError, EktProduct
from app.schemas.catalog import CatalogProductUpsert
from app.services.catalog import CatalogService

pytestmark = pytest.mark.asyncio


def local_product(article: str, *, name: str = "Cable", characteristics: dict | None = None):
    return SimpleNamespace(
        id=uuid4(), article=article, external_id=f"remote-{article}", name=name,
        description=f"{name} description", brand="EKT", characteristics=characteristics or {},
        cached_price=Decimal("99.00"), cached_stock_by_location={"old": 4}, cached_available=True,
    )


class FakeCatalogRepository:
    def __init__(self, products):
        self.products = products

    async def upsert(self, payload):
        return local_product(payload.article, name=payload.name, characteristics=payload.characteristics)

    async def find_by_article(self, article):
        return next((product for product in self.products if product.article == article), None)

    async def full_text_search(self, query, *, characteristics=None, limit=20):
        matches = self.products
        if query:
            matches = [p for p in matches if query.lower() in f"{p.name} {p.description} {p.brand}".lower()]
        if characteristics:
            matches = [p for p in matches if all(p.characteristics.get(k) == v for k, v in characteristics.items())]
        return matches[:limit]


class CurrentEkt:
    async def get_current_product_by_article(self, article):
        return EktProduct(
            id="remote-A-1", article=article, name="Cable", price=Decimal("105.50"),
            stock_by_location={"almaty": 3},
        )


class UnavailableEkt:
    async def get_current_product_by_article(self, article):
        raise EktConnectionError("unavailable")


async def test_exact_article_has_priority_over_text_search() -> None:
    exact = local_product("A-1", name="Cable exact")
    service = CatalogService(FakeCatalogRepository([exact, local_product("B-2", name="A-1 alternative")]))

    result = await service.search_candidates("A-1")

    assert result.match_type == "exact_article"
    assert [candidate.article for candidate in result.candidates] == ["A-1"]


async def test_full_text_search_returns_multiple_candidates_and_jsonb_filter() -> None:
    products = [
        local_product("A-1", name="Copper cable", characteristics={"cores": 3}),
        local_product("B-2", name="Copper cable", characteristics={"cores": 3}),
        local_product("C-3", name="Copper cable", characteristics={"cores": 2}),
    ]
    service = CatalogService(FakeCatalogRepository(products))

    result = await service.search_candidates("copper", characteristics={"cores": 3})

    assert result.match_type == "full_text"
    assert [candidate.article for candidate in result.candidates] == ["A-1", "B-2"]


async def test_missing_product_returns_no_candidates() -> None:
    service = CatalogService(FakeCatalogRepository([local_product("A-1")]))

    result = await service.search_candidates("unmatched")

    assert result.match_type == "none"
    assert result.candidates == []


async def test_save_product_returns_catalog_candidate() -> None:
    service = CatalogService(FakeCatalogRepository([]))

    result = await service.save_product(CatalogProductUpsert(article="A-1", name="Cable", characteristics={"cores": 3}))

    assert result.article == "A-1"


async def test_current_price_and_stock_come_from_ekt_not_local_cache() -> None:
    service = CatalogService(FakeCatalogRepository([]), ekt_client=CurrentEkt())

    result = await service.get_current_availability("A-1")

    assert result.current is True
    assert result.price == Decimal("105.50")
    assert result.stock_by_location == {"almaty": 3}
    assert result.available is True


async def test_ekt_unavailable_never_returns_cached_price_or_stock_as_current() -> None:
    service = CatalogService(FakeCatalogRepository([]), ekt_client=UnavailableEkt())

    result = await service.get_current_availability("A-1")

    assert result.current is False
    assert result.reason == "ekt_unavailable"
    assert result.price is None
    assert result.stock_by_location is None
