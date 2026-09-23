import re
from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.openapi import public_error_responses
from app.config.database import get_db
from app.integrations.catalog_adapter import build_catalog_adapter
from app.integrations.cart_gateway import build_cart_gateway
from app.repositories.catalog import CatalogRepository
from app.repositories.offers import OfferRepository
from app.schemas.offers import ConfirmOfferResult, CreateOfferRequest, PendingOfferView
from app.services.offers import OfferService
from app.services.catalog import CatalogService
from app.services.offer_product_provider import CatalogCurrentProductProvider

router = APIRouter(prefix="/api/chat/sessions/{session_id}/offers", tags=["offers"])


async def get_offer_service(session: AsyncSession = Depends(get_db)) -> AsyncGenerator[OfferService, None]:
    # No real EKT mapper or cart contract is available yet; both adapters fail closed.
    catalog = CatalogService(CatalogRepository(session), adapter=build_catalog_adapter())
    yield OfferService(OfferRepository(session), CatalogCurrentProductProvider(catalog), build_cart_gateway())


Offer = Annotated[OfferService, Depends(get_offer_service)]


@router.post(
    "",
    response_model=PendingOfferView,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_pending_offer",
    summary="Create a pending offer without modifying the cart",
    responses=public_error_responses(404, 409, 422, 502, 503),
)
async def create_offer(session_id: UUID, payload: CreateOfferRequest, service: Offer) -> PendingOfferView:
    return await service.create_offer(session_id, payload)


@router.post(
    "/{offer_id}/confirm",
    response_model=ConfirmOfferResult,
    operation_id="confirm_pending_offer",
    summary="Confirm one pending offer with an idempotency key",
    responses=public_error_responses(400, 404, 409, 422, 502, 503),
)
async def confirm_offer(
    session_id: UUID,
    offer_id: UUID,
    service: Offer,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
) -> ConfirmOfferResult:
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", idempotency_key):
        raise HTTPException(status_code=400, detail="Invalid Idempotency-Key")
    return await service.confirm_offer(session_id, offer_id, idempotency_key)
