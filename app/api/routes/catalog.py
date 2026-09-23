import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.integrations.catalog_adapter import build_catalog_adapter
from app.repositories.catalog import CatalogRepository
from app.schemas.catalog import (
    CatalogCandidate,
    CatalogIndexRefresh,
    CatalogProductUpsert,
    CatalogSearchResponse,
    CurrentAvailability,
    FreshCatalogProduct,
)
from app.services.catalog import CatalogService

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def get_catalog_service(session: AsyncSession = Depends(get_db)) -> CatalogService:
    return CatalogService(CatalogRepository(session), adapter=build_catalog_adapter())


Catalog = Annotated[CatalogService, Depends(get_catalog_service)]


@router.post("/products", response_model=CatalogCandidate)
async def save_product(payload: CatalogProductUpsert, service: Catalog) -> CatalogCandidate:
    return await service.save_product(payload)


@router.get("/search", response_model=CatalogSearchResponse)
async def search_products(
    service: Catalog,
    q: str | None = Query(default=None, max_length=500),
    characteristics: str | None = Query(default=None, max_length=4000),
    limit: int = Query(default=20, ge=1, le=100),
) -> CatalogSearchResponse:
    filters = _parse_characteristics(characteristics)
    return await service.search_candidates(q, characteristics=filters, limit=limit)


@router.get("/products/{article}/current", response_model=CurrentAvailability)
async def current_product_availability(article: str, service: Catalog) -> CurrentAvailability:
    return await service.get_current_availability(article)


@router.get("/products/{article}/fresh", response_model=FreshCatalogProduct)
async def fresh_product_details(article: str, service: Catalog) -> FreshCatalogProduct:
    return await service.get_fresh_product(article)


@router.post("/index/refresh", response_model=CatalogIndexRefresh)
async def refresh_catalog_index(
    service: Catalog,
    max_pages: int = Query(default=1000, ge=1, le=1000),
    page_size: int = Query(default=50, ge=1, le=1000),
) -> CatalogIndexRefresh:
    return await service.refresh_index(max_pages=max_pages, page_size=page_size)


def _parse_characteristics(value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="characteristics must be a JSON object") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=422, detail="characteristics must be a JSON object")
    return parsed
