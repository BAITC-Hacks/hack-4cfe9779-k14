import json
from typing import Annotated, Any
from collections.abc import AsyncGenerator

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.config.settings import get_settings
from app.integrations.catalog_adapter import build_catalog_adapter
from app.repositories.catalog import CatalogRepository
from app.schemas.catalog import (
    CatalogCandidate,
    CatalogSourcePage,
    CatalogIndexRefresh,
    CatalogProductUpsert,
    CatalogSearchResponse,
    CurrentAvailability,
    FreshCatalogProduct,
)
from app.services.catalog import CatalogService

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


async def get_catalog_service(session: AsyncSession = Depends(get_db)) -> AsyncGenerator[CatalogService, None]:
    adapter = build_catalog_adapter()
    try:
        yield CatalogService(CatalogRepository(session, source_origin="ekt/live" if get_settings().catalog_adapter_mode == "ekt" else "mock/demo"), adapter=adapter)
    finally:
        await adapter.aclose()


Catalog = Annotated[CatalogService, Depends(get_catalog_service)]


class RuntimeStatus(BaseModel):
    catalog_source: str
    model_configured: bool
    model: str | None
    cart_mode: str


@router.get("/status", response_model=RuntimeStatus)
async def runtime_status():
    settings = get_settings()
    configured = bool(settings.openai_api_key or (settings.llm_api_key and settings.llm_api_url and settings.llm_model))
    return RuntimeStatus(catalog_source=settings.catalog_adapter_mode, model_configured=configured,
                         model=settings.openai_model if settings.openai_api_key else settings.llm_model or None,
                         cart_mode=settings.cart_adapter_mode)


@router.post("/products", response_model=CatalogCandidate)
async def save_product(payload: CatalogProductUpsert, service: Catalog) -> CatalogCandidate:
    return await service.save_product(payload)


@router.get("/products", response_model=CatalogSearchResponse)
async def list_products(service: Catalog, limit: int = Query(default=100, ge=1, le=100)) -> CatalogSearchResponse:
    return await service.list_products(limit=limit)


@router.get("/source-page", response_model=CatalogSourcePage)
async def load_source_page(service: Catalog, page: int = Query(default=1, ge=1, le=10000)):
    return await service.load_source_page(page)


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
