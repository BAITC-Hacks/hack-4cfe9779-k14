from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.config.settings import get_settings
from app.integrations.cart_gateway import CartGateway, CartGatewayError
from app.integrations.ekt_client import EktClientError, EktProduct
from app.models.temporary import PendingOffer
from app.repositories.offers import OfferRepository
from app.schemas.offers import ConfirmOfferResult, CreateOfferRequest, PendingOfferStatus, PendingOfferView
from app.services.errors import OfferConflict, OfferPreconditionFailed, ResourceNotFound


class CurrentProductProvider(Protocol):
    async def get_current_product_by_article(self, article: str) -> EktProduct: ...


class OfferService:
    """Server-owned offer/confirmation workflow. LLM code must not call it directly."""

    def __init__(self, repository: OfferRepository, ekt_client: CurrentProductProvider, cart: CartGateway) -> None:
        self._repository = repository
        self._ekt_client = ekt_client
        self._cart = cart
        settings = get_settings()
        self._offer_ttl = timedelta(seconds=settings.pending_offer_ttl_seconds)
        self._idempotency_ttl = timedelta(seconds=settings.idempotency_key_ttl_seconds)

    async def create_offer(self, session_id: UUID, request: CreateOfferRequest) -> PendingOfferView:
        current = await self._get_current_product(request.article)
        self._require_current_product(current, request.product_identifier, request.article, request.quantity)
        now = self._now()
        offer = PendingOffer(
            session_id=session_id,
            product_identifier=request.product_identifier,
            article=request.article,
            quantity=request.quantity,
            price_at_offer=current.price,
            status=PendingOfferStatus.PENDING.value,
            payload={},
            expires_at=now + self._offer_ttl,
        )
        async with self._repository.transaction():
            if not await self._repository.session_exists(session_id):
                raise ResourceNotFound("Chat session was not found")
            await self._repository.create_offer(offer)
        return PendingOfferView.model_validate(offer)

    async def confirm_offer(self, session_id: UUID, offer_id: UUID, idempotency_key: str) -> ConfirmOfferResult:
        now = self._now()
        async with self._repository.transaction():
            offer = await self._repository.lock_offer(offer_id, session_id)
            if offer is None:
                raise ResourceNotFound("Pending offer was not found")

            scope = f"cart-confirm:{offer.id}"
            cached = await self._repository.lock_idempotency_key(scope, idempotency_key)
            if cached is not None and cached.response_payload is not None:
                return ConfirmOfferResult.model_validate(cached.response_payload)
            if cached is None:
                cached = await self._repository.reserve_idempotency_key(scope, idempotency_key, now + self._idempotency_ttl)

            if offer.status == PendingOfferStatus.CONFIRMED.value:
                result = self._result(offer, "already_confirmed", "This offer was already confirmed.")
                return await self._cache_result(cached, result)
            if offer.status != PendingOfferStatus.PENDING.value:
                raise OfferConflict(f"Offer cannot be confirmed from status {offer.status}")
            if offer.expires_at <= now:
                offer.status = PendingOfferStatus.EXPIRED.value
                result = self._result(offer, "expired", "Offer expired. Create a new offer.")
                return await self._cache_result(cached, result)

            try:
                current = await self._ekt_client.get_current_product_by_article(offer.article)
            except EktClientError:
                offer.status = PendingOfferStatus.FAILED.value
                result = self._result(offer, "ekt_unavailable", "Could not confirm current product data.")
                return await self._cache_result(cached, result)

            if current.id != offer.product_identifier or current.article.strip().casefold() != offer.article.strip().casefold():
                offer.status = PendingOfferStatus.REJECTED.value
                result = self._result(offer, "product_changed", "Product data no longer matches this offer.")
                return await self._cache_result(cached, result)
            if current.price is None or current.price < Decimal("0") or current.stock_by_location is None:
                offer.status = PendingOfferStatus.FAILED.value
                result = self._result(offer, "ekt_data_incomplete", "Could not confirm current price and stock.")
                return await self._cache_result(cached, result)
            if any(value < 0 for value in current.stock_by_location.values()) or sum(current.stock_by_location.values()) < offer.quantity:
                offer.status = PendingOfferStatus.REJECTED.value
                result = self._result(offer, "insufficient_stock", "Insufficient current stock.")
                return await self._cache_result(cached, result)
            if current.price != offer.price_at_offer:
                offer.status = PendingOfferStatus.REJECTED.value
                replacement = await self._create_replacement_offer(offer, current, now)
                result = self._result(
                    replacement,
                    "price_changed",
                    "Price changed. Confirm the new offer explicitly.",
                )
                return await self._cache_result(cached, result)

            try:
                cart_result = await self._cart.add_item(
                    session_id=session_id,
                    product_identifier=offer.product_identifier,
                    quantity=offer.quantity,
                    idempotency_key=idempotency_key,
                )
            except CartGatewayError:
                offer.status = PendingOfferStatus.FAILED.value
                result = self._result(offer, "cart_unavailable", "Cart could not be updated.")
                return await self._cache_result(cached, result)

            offer.status = PendingOfferStatus.CONFIRMED.value
            result = self._result(offer, "confirmed", "Product was added to the cart.", cart_url=cart_result.cart_url)
            return await self._cache_result(cached, result)

    async def _create_replacement_offer(self, offer: PendingOffer, current: EktProduct, now: datetime) -> PendingOffer:
        replacement = PendingOffer(
            session_id=offer.session_id,
            product_identifier=offer.product_identifier,
            article=offer.article,
            quantity=offer.quantity,
            price_at_offer=current.price,
            status=PendingOfferStatus.PENDING.value,
            payload={},
            expires_at=now + self._offer_ttl,
        )
        return await self._repository.create_offer(replacement)

    async def _cache_result(self, record, result: ConfirmOfferResult) -> ConfirmOfferResult:
        record.response_payload = result.model_dump(mode="json")
        await self._repository.save()
        return result

    async def _get_current_product(self, article: str) -> EktProduct:
        try:
            return await self._ekt_client.get_current_product_by_article(article)
        except EktClientError as exc:
            raise OfferPreconditionFailed("Could not confirm current product data") from exc

    @staticmethod
    def _require_current_product(current: EktProduct, identifier: str, article: str, quantity: int) -> None:
        if current.id != identifier or current.article.strip().casefold() != article.strip().casefold():
            raise OfferPreconditionFailed("Current product does not match the requested product")
        if current.price is None or current.price < Decimal("0") or current.stock_by_location is None:
            raise OfferPreconditionFailed("Current price and stock are required before creating an offer")
        if any(value < 0 for value in current.stock_by_location.values()) or sum(current.stock_by_location.values()) < quantity:
            raise OfferPreconditionFailed("Insufficient current stock")

    @staticmethod
    def _result(offer: PendingOffer, outcome: str, message: str, cart_url: str | None = None) -> ConfirmOfferResult:
        return ConfirmOfferResult(
            offer=PendingOfferView.model_validate(offer), outcome=outcome, message=message, cart_url=cart_url
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
