from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.integrations.catalog_adapter import (
    CatalogAdapterMalformedResponseError,
    EktCatalogAdapter,
    MockCatalogAdapter,
)
from app.integrations.ekt_client import EktProduct
from app.schemas.catalog import CatalogProductUpsert
from app.services.catalog import CatalogService

pytestmark = pytest.mark.asyncio


def dataset_path() -> Path:
    return Path(__file__).parents[1] / "testdata" / "mock_catalog.json"


def stored_product(payload: CatalogProductUpsert) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), **payload.model_dump())


class MemoryCatalogRepository:
    def __init__(self, products: list[SimpleNamespace] | None = None) -> None:
        self.products = products or []

    async def upsert(self, payload: CatalogProductUpsert) -> SimpleNamespace:
        product = stored_product(payload)
        self.products = [item for item in self.products if item.article != payload.article]
        self.products.append(product)
        return product

    async def find_by_article(self, article: str) -> SimpleNamespace | None:
        return next((item for item in self.products if item.article == article), None)

    async def full_text_search(self, query, *, characteristics=None, limit=20):
        results = self.products
        if query:
            needle = query.casefold()
            results = [
                item
                for item in results
                if needle in " ".join(
                    str(value or "")
                    for value in (item.name, item.category, item.description, item.brand, item.characteristics, item.source_fields)
                ).casefold()
            ]
        if characteristics:
            results = [
                item for item in results
                if all(item.characteristics.get(key) == value for key, value in characteristics.items())
            ]
        return results[:limit]


async def test_mock_adapter_exact_sku_is_exact_and_unknown_is_not_a_near_match() -> None:
    adapter = MockCatalogAdapter.from_file(dataset_path())

    product = await adapter.get_product_by_article("demo-cable-vvg-3x2-5")

    assert product.article == "DEMO-CABLE-VVG-3X2-5"
    assert product.cached_stock_by_location == {"Алматы": 120, "Астана": 45}
    with pytest.raises(Exception) as error:
        await adapter.get_product_by_article("DEMO-UNKNOWN-404")
    assert getattr(error.value, "code") == "catalog_not_found"


async def test_mock_adapter_paginates_and_preserves_present_null_vs_missing_fields() -> None:
    adapter = MockCatalogAdapter.from_file(dataset_path())

    first = await adapter.get_products_page(1, page_size=2)
    second = await adapter.get_products_page(2, page_size=2)
    unknown_certificate = await adapter.get_product_by_article("DEMO-CABLE-VVG-2X2-5")

    assert [product.article for product in first.products] == ["DEMO-CABLE-VVG-3X2-5", "DEMO-CABLE-VVG-3X1-5"]
    assert first.has_more is True
    assert len(second.products) == 2 and second.has_more is False
    assert unknown_certificate.certificates is None
    assert unknown_certificate.source_field_presence["certificates"] is True
    assert unknown_certificate.source_field_presence["description"] is False


async def test_index_searches_name_category_and_specifications_with_adapter_independence() -> None:
    adapter = MockCatalogAdapter.from_file(dataset_path())
    repository = MemoryCatalogRepository()
    service = CatalogService(repository, adapter=adapter)

    refreshed = await service.refresh_index(page_size=2)
    by_name = await service.search_candidates("ВВГнг")
    by_category = await service.search_candidates("Кабель и провод")
    by_specification = await service.search_candidates(None, characteristics={"material": "алюминий"})

    assert refreshed.products_loaded == 4
    assert refreshed.pages_loaded == 2
    assert len(by_name.candidates) == 3
    assert len(by_category.candidates) == 4
    assert [item.article for item in by_specification.candidates] == ["DEMO-CABLE-AL-3X2-5"]


async def test_unknown_sku_does_not_fall_through_to_text_search() -> None:
    adapter = MockCatalogAdapter.from_file(dataset_path())
    repository = MemoryCatalogRepository([
        stored_product(CatalogProductUpsert(article="LOCAL-1", name="DEMO-UNKNOWN-404 compatible cable")),
    ])
    service = CatalogService(repository, adapter=adapter)

    result = await service.search_candidates("DEMO-UNKNOWN-404")

    assert result.match_type == "none"
    assert result.candidates == []


async def test_fresh_details_return_only_adapter_values_for_stocks_and_certificates() -> None:
    repository = MemoryCatalogRepository()
    service = CatalogService(repository, adapter=MockCatalogAdapter.from_file(dataset_path()))

    certified = await service.get_fresh_product("DEMO-CABLE-VVG-3X2-5")
    without_certificate = await service.get_fresh_product("DEMO-CABLE-VVG-3X1-5")
    unknown_availability = await service.get_fresh_product("DEMO-CABLE-AL-3X2-5")

    assert certified.certificates == [{"type": "соответствие", "number": "DEMO-CERT-001"}]
    assert certified.cached_stock_by_location == {"Алматы": 120, "Астана": 45}
    assert without_certificate.certificates == []
    assert unknown_availability.cached_price is None
    assert unknown_availability.cached_stock_by_location is None
    assert unknown_availability.cached_available is None


async def test_mock_adapter_rejects_malformed_data(tmp_path: Path) -> None:
    malformed = tmp_path / "bad.json"
    malformed.write_text('{"products": [{"article": "missing-name"}]}', encoding="utf-8")

    with pytest.raises(CatalogAdapterMalformedResponseError):
        MockCatalogAdapter.from_file(malformed)


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
