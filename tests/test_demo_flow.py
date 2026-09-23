from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.integrations.ekt_client import EktProduct
from app.schemas.catalog import CatalogCandidate, CatalogSearchResponse, CurrentAvailability
from app.schemas.chat import ChatAnalysis, ChatIntent, ChatMessageCreate, ChatRole
from app.schemas.offers import CartItem, CartReference, CartSnapshot, CartWriteResult, CreateOfferRequest
from app.services.chat import ChatService
from app.services.offers import OfferService

pytestmark = pytest.mark.asyncio


class ChatRepository:
    def __init__(self) -> None:
        self.session_id = uuid4()
        self.messages = []

    async def get_session(self, session_id):
        return SimpleNamespace(id=session_id) if session_id == self.session_id else None

    async def add_message(self, session_id, role, content, metadata=None):
        message = SimpleNamespace(
            id=uuid4(), session_id=session_id, role=role.value, content=content,
            created_at=datetime.now(timezone.utc), metadata_json=metadata or {},
        )
        self.messages.append(message)
        return message

    async def history(self, session_id, *, limit=None):
        result = [item for item in self.messages if item.session_id == session_id]
        return result[-limit:] if limit else result


class Catalog:
    def __init__(self) -> None:
        self.candidate = CatalogCandidate(
            id=uuid4(), article="A-1", external_id="ekt-1", name="Copper cable", description=None,
            brand="EKT", category="Cable", characteristics={}, cached_price=None, cached_stock_by_location=None,
            cached_available=None, certificates=None, source_fields=None,
        )

    async def search_candidates(self, query, *, characteristics=None, limit=20):
        del characteristics, limit
        return CatalogSearchResponse(candidates=[self.candidate] if query == "A-1" else [], match_type="exact_article")

    async def get_current_availability(self, article):
        return CurrentAvailability(article=article, price=Decimal("10.00"), stock_by_location={"A": 4}, available=True, current=True)


class Llm:
    async def analyze(self, history, attachment_data=None):
        del history, attachment_data
        return ChatAnalysis(intent=ChatIntent.FIND_PRODUCT, article="A-1", quantity=2)


class OfferRepository:
    def __init__(self) -> None:
        self.offers = {}
        self.keys = {}

    @asynccontextmanager
    async def transaction(self):
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
        return self.keys.get((scope, key))

    async def reserve_idempotency_key(self, scope, key, expires_at):
        record = SimpleNamespace(response_payload=None, expires_at=expires_at)
        self.keys[(scope, key)] = record
        return record

    async def save(self):
        return None


class Ekt:
    def __init__(self) -> None:
        self.calls = 0

    async def get_current_product_by_article(self, article):
        self.calls += 1
        return EktProduct(id="ekt-1", article=article, name="Copper cable", price=Decimal("10.00"), stock_by_location={"A": 4})


class Cart:
    def __init__(self) -> None:
        self.calls = 0
        self.read_calls = 0
        self.items = {}

    source_label = "demo test cart"

    async def resolve_cart(self, *, session_id):
        return CartReference(cart_id=f"cart-{session_id}", owner_session_id=session_id)

    async def add_item(self, *, cart, product_identifier, quantity, idempotency_key):
        self.calls += 1
        self.items[product_identifier] = self.items.get(product_identifier, 0) + quantity
        return CartWriteResult(cart_id=cart.cart_id, operation_id=idempotency_key)

    async def set_item_quantity(self, *, cart, product_identifier, quantity, idempotency_key):
        self.items[product_identifier] = quantity
        return CartWriteResult(cart_id=cart.cart_id, operation_id=idempotency_key)

    async def get_cart(self, *, cart):
        self.read_calls += 1
        return CartSnapshot(
            cart_id=cart.cart_id,
            items=[CartItem(product_identifier=key, quantity=value) for key, value in self.items.items()],
            cart_url="https://cart.example/current",
            source_label=self.source_label,
        )


async def test_chat_catalog_offer_confirmation_journey_uses_test_doubles() -> None:
    chat_repository = ChatRepository()
    catalog = Catalog()
    chat = ChatService(chat_repository, catalog, Llm())

    reply = await chat.send_message(chat_repository.session_id, ChatMessageCreate(content="Нужен A-1, 2 штуки"))

    assert reply.candidates[0].article == "A-1"
    ekt, cart = Ekt(), Cart()
    offers = OfferService(OfferRepository(), ekt, cart)
    offer = await offers.create_offer(
        chat_repository.session_id,
        CreateOfferRequest(product_identifier="ekt-1", article="A-1", quantity=2),
    )
    confirmation = await offers.confirm_offer(chat_repository.session_id, offer.offer_id, "test-key-1")

    assert confirmation.outcome == "confirmed"
    assert confirmation.cart_url == "https://cart.example/current"
    assert ekt.calls == 2  # offer creation and the mandatory confirmation recheck
    assert cart.calls == 1
    assert cart.read_calls == 1
