import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.integrations.cart_gateway import CartUnavailableError
from app.integrations.ekt_client import EktConnectionError, EktProduct
from app.schemas.offers import CreateOfferRequest, PendingOfferStatus
from app.services.offers import OfferService

pytestmark = pytest.mark.asyncio


class FakeOfferRepository:
    def __init__(self) -> None:
        self.offers = {}
        self.idempotency = {}
        self.lock = asyncio.Lock()

    @asynccontextmanager
    async def transaction(self):
        async with self.lock:
            yield

    async def session_exists(self, session_id):
        return True

    async def create_offer(self, offer):
        offer.id = uuid4()
        offer.created_at = datetime.now(timezone.utc)
        self.offers[offer.id] = offer
        return offer

    async def lock_offer(self, offer_id, session_id):
        offer = self.offers.get(offer_id)
        return offer if offer and offer.session_id == session_id else None

    async def lock_idempotency_key(self, scope, key):
        return self.idempotency.get((scope, key))

    async def reserve_idempotency_key(self, scope, key, expires_at):
        record = SimpleNamespace(scope=scope, key=key, expires_at=expires_at, response_payload=None)
        self.idempotency[(scope, key)] = record
        return record

    async def save(self):
        return None


class FakeEkt:
    def __init__(self, product=None, error=None):
        self.product = product or EktProduct(
            id="product-1", article="A-1", name="Cable", price=Decimal("10.00"), stock_by_location={"A": 5}
        )
        self.error = error
        self.calls = 0

    async def get_current_product_by_article(self, article):
        self.calls += 1
        if self.error:
            raise self.error
        return self.product


class FakeCart:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    async def add_item(self, **kwargs):
        self.calls.append(kwargs)
        await asyncio.sleep(0)
        if self.error:
            raise self.error
        from app.schemas.offers import CartWriteResult

        return CartWriteResult(cart_url="https://cart.invalid/current")


async def create_offer(service, session_id):
    return await service.create_offer(session_id, CreateOfferRequest(product_identifier="product-1", article="A-1", quantity=2))


async def test_successful_confirmation_rechecks_and_writes_cart() -> None:
    repository, ekt, cart = FakeOfferRepository(), FakeEkt(), FakeCart()
    service = OfferService(repository, ekt, cart)
    session_id = uuid4()
    offer = await create_offer(service, session_id)

    result = await service.confirm_offer(session_id, offer.offer_id, "idem-key-1")

    assert result.outcome == "confirmed"
    assert result.offer.status == PendingOfferStatus.CONFIRMED
    assert result.cart_url == "https://cart.invalid/current"
    assert len(cart.calls) == 1
    assert ekt.calls == 2  # create + confirmation recheck


async def test_same_idempotency_key_does_not_add_twice() -> None:
    repository, ekt, cart = FakeOfferRepository(), FakeEkt(), FakeCart()
    service = OfferService(repository, ekt, cart)
    session_id = uuid4()
    offer = await create_offer(service, session_id)

    first = await service.confirm_offer(session_id, offer.offer_id, "idem-key-1")
    second = await service.confirm_offer(session_id, offer.offer_id, "idem-key-1")

    assert first == second
    assert len(cart.calls) == 1


async def test_expired_offer_is_not_written_to_cart() -> None:
    repository, ekt, cart = FakeOfferRepository(), FakeEkt(), FakeCart()
    service = OfferService(repository, ekt, cart)
    session_id = uuid4()
    offer = await create_offer(service, session_id)
    repository.offers[offer.offer_id].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    result = await service.confirm_offer(session_id, offer.offer_id, "idem-key-1")

    assert result.outcome == "expired"
    assert result.offer.status == PendingOfferStatus.EXPIRED
    assert cart.calls == []


async def test_price_change_creates_new_offer_and_requires_new_confirmation() -> None:
    repository, ekt, cart = FakeOfferRepository(), FakeEkt(), FakeCart()
    service = OfferService(repository, ekt, cart)
    session_id = uuid4()
    offer = await create_offer(service, session_id)
    ekt.product = ekt.product.model_copy(update={"price": Decimal("12.00")})

    result = await service.confirm_offer(session_id, offer.offer_id, "idem-key-1")

    assert result.outcome == "price_changed"
    assert result.offer.offer_id != offer.offer_id
    assert result.offer.status == PendingOfferStatus.PENDING
    assert result.offer.price_at_offer == Decimal("12.00")
    assert cart.calls == []
    assert repository.offers[offer.offer_id].status == PendingOfferStatus.REJECTED.value


async def test_insufficient_stock_rejects_offer_without_cart_write() -> None:
    repository, ekt, cart = FakeOfferRepository(), FakeEkt(), FakeCart()
    service = OfferService(repository, ekt, cart)
    session_id = uuid4()
    offer = await create_offer(service, session_id)
    ekt.product = ekt.product.model_copy(update={"stock_by_location": {"A": 1}})

    result = await service.confirm_offer(session_id, offer.offer_id, "idem-key-1")

    assert result.outcome == "insufficient_stock"
    assert result.offer.status == PendingOfferStatus.REJECTED
    assert cart.calls == []


async def test_insufficient_stock_wins_over_simultaneous_price_change() -> None:
    repository, ekt, cart = FakeOfferRepository(), FakeEkt(), FakeCart()
    service = OfferService(repository, ekt, cart)
    session_id = uuid4()
    offer = await create_offer(service, session_id)
    ekt.product = ekt.product.model_copy(update={"price": Decimal("12.00"), "stock_by_location": {"A": 1}})

    result = await service.confirm_offer(session_id, offer.offer_id, "idem-key-1")

    assert result.outcome == "insufficient_stock"
    assert len(repository.offers) == 1
    assert cart.calls == []


async def test_ekt_error_marks_offer_failed_without_using_stale_data() -> None:
    repository, ekt, cart = FakeOfferRepository(), FakeEkt(), FakeCart()
    service = OfferService(repository, ekt, cart)
    session_id = uuid4()
    offer = await create_offer(service, session_id)
    ekt.error = EktConnectionError("offline")

    result = await service.confirm_offer(session_id, offer.offer_id, "idem-key-1")

    assert result.outcome == "ekt_unavailable"
    assert result.offer.status == PendingOfferStatus.FAILED
    assert cart.calls == []


async def test_two_concurrent_confirmations_write_cart_once() -> None:
    repository, ekt, cart = FakeOfferRepository(), FakeEkt(), FakeCart()
    service = OfferService(repository, ekt, cart)
    session_id = uuid4()
    offer = await create_offer(service, session_id)

    first, second = await asyncio.gather(
        service.confirm_offer(session_id, offer.offer_id, "idem-key-1"),
        service.confirm_offer(session_id, offer.offer_id, "idem-key-2"),
    )

    assert {first.outcome, second.outcome} == {"confirmed", "already_confirmed"}
    assert len(cart.calls) == 1
