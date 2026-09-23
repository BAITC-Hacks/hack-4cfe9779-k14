import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.repositories.catalog import CatalogRepository
from app.schemas.catalog import CatalogCandidate, CatalogProductUpsert, CatalogSearchResponse, CurrentAvailability
from app.services.catalog import CatalogService

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def get_catalog_service(session: AsyncSession = Depends(get_db)) -> CatalogService:
    return CatalogService(CatalogRepository(session))


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
