import re
from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config.database import SessionLocal
from app.integrations.catalog_adapter import build_catalog_adapter
from app.integrations.cart_gateway import build_cart_gateway
from app.repositories.catalog import CatalogRepository
from app.repositories.offers import OfferRepository
from app.schemas.offers import ConfirmOfferResult, CreateOfferRequest, PendingOfferView
from app.services.offers import OfferService
from app.services.catalog import CatalogService
from app.services.offer_product_provider import CatalogCurrentProductProvider

router = APIRouter(prefix="/api/chat/sessions/{session_id}/offers", tags=["offers"])


async def get_offer_service() -> AsyncGenerator[OfferService, None]:
    # Offer transactions own their session. Catalog lookups can autobegin a
    # read transaction and must not interfere with offer locks/commits.
    adapter = build_catalog_adapter()
    try:
        async with SessionLocal() as offer_session, SessionLocal() as catalog_session:
            catalog = CatalogService(CatalogRepository(catalog_session, source_origin="ekt/live"), adapter=adapter)
            yield OfferService(OfferRepository(offer_session), CatalogCurrentProductProvider(catalog), build_cart_gateway())
    finally:
        await adapter.aclose()


Offer = Annotated[OfferService, Depends(get_offer_service)]


@router.post("", response_model=PendingOfferView, status_code=status.HTTP_201_CREATED)
async def create_offer(session_id: UUID, payload: CreateOfferRequest, service: Offer) -> PendingOfferView:
    return await service.create_offer(session_id, payload)


@router.post("/{offer_id}/confirm", response_model=ConfirmOfferResult)
async def confirm_offer(
    session_id: UUID,
    offer_id: UUID,
    service: Offer,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
) -> ConfirmOfferResult:
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", idempotency_key):
        raise HTTPException(status_code=400, detail="Invalid Idempotency-Key")
    return await service.confirm_offer(session_id, offer_id, idempotency_key)
