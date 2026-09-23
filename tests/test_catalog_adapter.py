from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.integrations.catalog_adapter import CatalogAdapterNotFoundError, EktCatalogAdapter
from app.integrations.ekt_client import EktProduct
from app.schemas.catalog import CatalogPage, CatalogProductUpsert
from app.services.catalog import CatalogService

pytestmark = pytest.mark.asyncio


def products() -> list[CatalogProductUpsert]:
    return [
        CatalogProductUpsert(
            article="TEST-CABLE-3X2-5", external_id="source-1", name="Cable 3x2.5", category="Cable",
            characteristics={"cores": 3, "section": 2.5}, cached_stock_by_location={"A": 3},
            cached_available=True, certificates=[{"number": "CERT-1"}], source_field_presence={"certificates": True},
        ),
        CatalogProductUpsert(
            article="TEST-CABLE-3X1-5", external_id="source-2", name="Cable 3x1.5", category="Cable",
            characteristics={"cores": 3, "section": 1.5}, cached_stock_by_location={"A": 0},
            cached_available=False, certificates=[], source_field_presence={"certificates": True},
        ),
        CatalogProductUpsert(
            article="TEST-CABLE-2X2-5", external_id="source-3", name="Cable 2x2.5", category="Cable",
            characteristics={"cores": 2, "section": 2.5}, certificates=None,
            source_field_presence={"certificates": False},
        ),
    ]


class StaticTestAdapter:
    """Test-only adapter double; it is not importable from application runtime."""

    def __init__(self, entries: list[CatalogProductUpsert]) -> None:
        self._entries = entries

    async def get_product_by_article(self, article: str) -> CatalogProductUpsert:
        for item in self._entries:
            if item.article.casefold() == article.casefold():
                return item
        raise CatalogAdapterNotFoundError("not found")

    async def get_product_details(self, external_id: str) -> CatalogProductUpsert:
        for item in self._entries:
            if item.external_id == external_id:
                return item
        raise CatalogAdapterNotFoundError("not found")

    async def get_products_page(self, page: int = 1, *, page_size: int = 50) -> CatalogPage:
        start = (page - 1) * page_size
        return CatalogPage(page=page, products=self._entries[start : start + page_size], has_more=start + page_size < len(self._entries))

    async def aclose(self) -> None:
        return None


def stored_product(payload: CatalogProductUpsert) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), **payload.model_dump())


class MemoryCatalogRepository:
    def __init__(self) -> None:
        self.products: list[SimpleNamespace] = []

    async def upsert(self, payload: CatalogProductUpsert) -> SimpleNamespace:
        item = stored_product(payload)
        self.products = [existing for existing in self.products if existing.article != item.article]
        self.products.append(item)
        return item

    async def find_by_article(self, article: str) -> SimpleNamespace | None:
        return next((item for item in self.products if item.article == article), None)

    async def full_text_search(self, query, *, characteristics=None, limit=20):
        values = self.products
        if query:
            values = [item for item in values if query.casefold() in str(item.model_dump() if hasattr(item, "model_dump") else item.__dict__).casefold()]
        if characteristics:
            values = [item for item in values if all(item.characteristics.get(key) == value for key, value in characteristics.items())]
        return values[:limit]


async def test_adapter_contract_supports_exact_lookup_and_pagination() -> None:
    adapter = StaticTestAdapter(products())

    exact = await adapter.get_product_by_article("test-cable-3x2-5")
    page = await adapter.get_products_page(1, page_size=2)

    assert exact.article == "TEST-CABLE-3X2-5"
    assert [item.article for item in page.products] == ["TEST-CABLE-3X2-5", "TEST-CABLE-3X1-5"]
    assert page.has_more is True
    with pytest.raises(CatalogAdapterNotFoundError):
        await adapter.get_product_by_article("UNKNOWN-404")


async def test_catalog_index_search_and_fresh_fields_use_only_adapter_values() -> None:
    repository = MemoryCatalogRepository()
    service = CatalogService(repository, adapter=StaticTestAdapter(products()))

    refreshed = await service.refresh_index(page_size=2)
    by_name = await service.search_candidates("Cable")
    by_specification = await service.search_candidates(None, characteristics={"cores": 2})
    fresh = await service.get_fresh_product("TEST-CABLE-3X2-5")

    assert refreshed.products_loaded == 3
    assert len(by_name.candidates) == 3
    assert [item.article for item in by_specification.candidates] == ["TEST-CABLE-2X2-5"]
    assert fresh.certificates == [{"number": "CERT-1"}]


class FakeEktClient:
    async def get_current_product_by_article(self, article: str) -> EktProduct:
        return EktProduct(
            id="partner-1", article=article, name="Partner cable", price="20.00",
            stock_by_location={"A": 2, "B": 0}, attributes={"cores": 3},
            certificates=[], source_field_presence={"certificates": True, "stock_by_location": True},
        )

    async def get_product_details(self, external_id: str) -> EktProduct:
        return await self.get_current_product_by_article("PARTNER-1")

    async def get_products_page(self, page: int) -> list[EktProduct]:
        return [await self.get_current_product_by_article("PARTNER-1")] if page == 1 else []

    async def aclose(self) -> None:
        return None


async def test_ekt_adapter_normalizes_only_known_mapper_values() -> None:
    adapter = EktCatalogAdapter(FakeEktClient())  # type: ignore[arg-type]

    product = await adapter.get_product_by_article("PARTNER-1")
    page = await adapter.get_products_page(1)

    assert product.external_id == "partner-1"
    assert product.characteristics == {"cores": 3}
    assert product.cached_available is None
    assert product.certificates == []
    assert product.source_field_presence["certificates"] is True
    assert page.has_more is True
