from fastapi.testclient import TestClient
from types import SimpleNamespace
from uuid import uuid4
from decimal import Decimal

from app.api.routes.catalog import get_catalog_service
from app.main import app
from app.schemas.catalog import CatalogSearchResponse


class ApiCatalogService:
    async def save_product(self, payload):
        from app.schemas.catalog import CatalogCandidate

        return CatalogCandidate.model_validate(SimpleNamespace(
            id=uuid4(), article=payload.article, external_id=None, name=payload.name,
            description=None, brand=None, category=None, characteristics={}, cached_price=Decimal("1"),
            cached_stock_by_location=None, cached_available=None, certificates=None, source_fields=None,
        ))

    async def search_candidates(self, query, *, characteristics=None, limit=20):
        return CatalogSearchResponse(candidates=[], match_type="none")

    async def get_current_availability(self, article):
        from app.schemas.catalog import CurrentAvailability

        return CurrentAvailability(article=article, price=None, stock_by_location=None, available=None, current=False)

    async def get_fresh_product(self, article):
        from app.schemas.catalog import FreshCatalogProduct

        return FreshCatalogProduct(article=article, name="Fresh cable", certificates=[], fresh=True)

    async def refresh_index(self, *, max_pages=1000, page_size=50):
        from app.schemas.catalog import CatalogIndexRefresh

        return CatalogIndexRefresh(pages_loaded=1, products_loaded=4)


def test_catalog_endpoints_are_available_without_direct_orm_access() -> None:
    app.dependency_overrides[get_catalog_service] = lambda: ApiCatalogService()
    try:
        with TestClient(app) as client:
            created = client.post("/api/catalog/products", json={"article": "A-1", "name": "Cable"})
            searched = client.get("/api/catalog/search", params={"q": "cable"})
            current = client.get("/api/catalog/products/A-1/current")
            fresh = client.get("/api/catalog/products/A-1/fresh")
            refreshed = client.post("/api/catalog/index/refresh")
        assert created.status_code == 200
        assert created.json()["article"] == "A-1"
        assert searched.status_code == 200
        assert current.status_code == 200
        assert current.json()["current"] is False
        assert fresh.status_code == 200
        assert fresh.json()["fresh"] is True
        assert refreshed.json() == {"pages_loaded": 1, "products_loaded": 4}
    finally:
        app.dependency_overrides.clear()


def test_catalog_rejects_non_object_jsonb_filter() -> None:
    app.dependency_overrides[get_catalog_service] = lambda: ApiCatalogService()
    try:
        with TestClient(app) as client:
            response = client.get("/api/catalog/search", params={"characteristics": "[]"})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
