from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.integrations.llm_client import LLMUnavailableError
from app.schemas.catalog import CatalogCandidate, CatalogSearchResponse, CurrentAvailability, FreshCatalogProduct
from app.schemas.chat import ChatMessageCreate, ChatRole
from app.services.chat import ChatService
from app.services.errors import CatalogUnavailable

pytestmark = pytest.mark.asyncio


def candidate(article: str, name: str) -> CatalogCandidate:
    return CatalogCandidate(
        id=uuid4(), article=article, external_id=f"external-{article}", name=name, description=None,
        brand="Demo", category="Кабель", characteristics={"cores": 3}, cached_price=None,
        cached_stock_by_location=None, cached_available=None, certificates=None, source_fields=None,
    )


class SessionRepository:
    def __init__(self) -> None:
        self.session_ids = {uuid4(), uuid4()}
        self.messages: list[SimpleNamespace] = []

    async def get_session(self, session_id: UUID):
        return SimpleNamespace(id=session_id) if session_id in self.session_ids else None

    async def add_message(self, session_id, role, content, metadata=None):
        message = SimpleNamespace(
            id=uuid4(), session_id=session_id, role=role.value, content=content,
            created_at=datetime.now(timezone.utc), metadata_json=metadata or {},
        )
        self.messages.append(message)
        return message

    async def history(self, session_id, *, limit=None):
        messages = [message for message in self.messages if message.session_id == session_id]
        return messages[-limit:] if limit else messages


class DialogueCatalog:
    def __init__(self) -> None:
        self.products = {
            "ABC-123": FreshCatalogProduct(
                article="ABC-123", external_id="external-ABC-123", name="Кабель ABC", characteristics={"cores": 3},
                cached_price=Decimal("100.00"), cached_stock_by_location={"Алматы": 5, "Астана": 2},
                cached_available=True, certificates=[{"number": "CERT-ABC"}],
                source_field_presence={"characteristics": True, "certificates": True},
            ),
            "DEF-456": FreshCatalogProduct(
                article="DEF-456", external_id="external-DEF-456", name="Кабель DEF", characteristics={},
                cached_price=None, cached_stock_by_location={"Алматы": 0}, cached_available=False,
                certificates=None, source_field_presence={"characteristics": True, "certificates": False},
            ),
        }
        self.fresh_calls: list[str] = []
        self.current_calls: list[str] = []

    async def search_candidates(self, query, *, characteristics=None, limit=20):
        del characteristics, limit
        if query in self.products:
            product = self.products[query]
            return CatalogSearchResponse(candidates=[candidate(product.article, product.name)], match_type="exact_article")
        if query and "кабель" in query.casefold():
            return CatalogSearchResponse(
                candidates=[candidate("ABC-123", "Кабель ABC"), candidate("DEF-456", "Кабель DEF")], match_type="full_text",
            )
        return CatalogSearchResponse(candidates=[], match_type="none")

    async def get_fresh_product(self, article):
        self.fresh_calls.append(article)
        if article not in self.products:
            from app.services.errors import ResourceNotFound
            raise ResourceNotFound("missing")
        return self.products[article]

    async def get_current_availability(self, article):
        self.current_calls.append(article)
        product = self.products.get(article)
        if product is None:
            return CurrentAvailability(article=article, price=None, stock_by_location=None, available=None, current=False, reason="unknown_sku")
        return CurrentAvailability(
            article=article, price=product.cached_price, stock_by_location=product.cached_stock_by_location,
            available=product.cached_available, current=True,
        )


class UnusedLLM:
    async def analyze(self, history, attachment_data=None):
        raise AssertionError("deterministic route should not invoke LLM")

    async def aclose(self):
        return None


class FailingLLM:
    async def analyze(self, history, attachment_data=None):
        raise LLMUnavailableError("offline")

    async def aclose(self):
        return None


async def test_sku_follow_up_certificate_uses_session_context_and_fresh_catalog_data() -> None:
    repository, catalog = SessionRepository(), DialogueCatalog()
    session_id = next(iter(repository.session_ids))
    service = ChatService(repository, catalog, UnusedLLM())

    found = await service.send_message(session_id, ChatMessageCreate(content="Найди ABC-123"))
    certificate = await service.send_message(session_id, ChatMessageCreate(content="А сертификат у него есть?"))

    assert found.candidates[0]["article"] == "ABC-123"
    assert "CERT-ABC" in certificate.assistant_message.content
    assert catalog.fresh_calls == ["ABC-123"]


async def test_availability_follow_up_uses_selected_product_and_current_service() -> None:
    repository, catalog = SessionRepository(), DialogueCatalog()
    session_id = next(iter(repository.session_ids))
    service = ChatService(repository, catalog, UnusedLLM())

    await service.send_message(session_id, ChatMessageCreate(content="Найди DEF-456"))
    reply = await service.send_message(session_id, ChatMessageCreate(content="А наличие?"))

    assert catalog.current_calls == ["DEF-456"]
    assert "нет в наличии" in reply.assistant_message.content
    assert "Алматы: 0" in reply.assistant_message.content


async def test_ambiguous_search_requests_clarification_instead_of_selecting_a_product() -> None:
    repository, catalog = SessionRepository(), DialogueCatalog()
    session_id = next(iter(repository.session_ids))
    service = ChatService(repository, catalog, UnusedLLM())

    reply = await service.send_message(session_id, ChatMessageCreate(content="Найди кабель"))

    assert len(reply.candidates) == 2
    assert "Укажите точный артикул" in reply.assistant_message.content
    assert repository.messages[-1].metadata_json["dialogue_context"]["selected_article"] is None


async def test_unknown_sku_is_not_replaced_by_similar_product() -> None:
    repository, catalog = SessionRepository(), DialogueCatalog()
    session_id = next(iter(repository.session_ids))
    service = ChatService(repository, catalog, UnusedLLM())

    reply = await service.send_message(session_id, ChatMessageCreate(content="Найди UNKNOWN-404"))

    assert reply.candidates == []
    assert "не найдено" in reply.assistant_message.content


async def test_missing_certificate_field_is_reported_as_missing_not_absent_certificate() -> None:
    repository, catalog = SessionRepository(), DialogueCatalog()
    session_id = next(iter(repository.session_ids))
    service = ChatService(repository, catalog, UnusedLLM())

    reply = await service.send_message(session_id, ChatMessageCreate(content="Сертификат DEF-456"))

    assert "не предоставил данные" in reply.assistant_message.content


async def test_purchase_conditions_report_unavailable_without_approved_provider() -> None:
    repository, catalog = SessionRepository(), DialogueCatalog()
    session_id = next(iter(repository.session_ids))
    service = ChatService(repository, catalog, UnusedLLM())

    reply = await service.send_message(session_id, ChatMessageCreate(content="Какие условия доставки и оплаты?"))

    assert reply.purchase_conditions is not None
    assert "не предоставлены" in reply.assistant_message.content


async def test_context_is_isolated_between_two_sessions() -> None:
    repository, catalog = SessionRepository(), DialogueCatalog()
    first, second = tuple(repository.session_ids)
    service = ChatService(repository, catalog, UnusedLLM())

    await service.send_message(first, ChatMessageCreate(content="Найди ABC-123"))
    await service.send_message(second, ChatMessageCreate(content="Найди DEF-456"))
    first_reply = await service.send_message(first, ChatMessageCreate(content="Сертификат у него?"))
    second_reply = await service.send_message(second, ChatMessageCreate(content="Сертификат у него?"))

    assert "CERT-ABC" in first_reply.assistant_message.content
    assert "не предоставил данные" in second_reply.assistant_message.content
    assert catalog.fresh_calls == ["ABC-123", "DEF-456"]


async def test_llm_failure_returns_safe_clarification_without_catalog_claims() -> None:
    repository, catalog = SessionRepository(), DialogueCatalog()
    session_id = next(iter(repository.session_ids))
    service = ChatService(repository, catalog, FailingLLM())

    reply = await service.send_message(session_id, ChatMessageCreate(content="Расскажи что-нибудь интересное"))

    assert reply.analysis.intent.value == "unknown"
    assert "Не удалось обработать" in reply.assistant_message.content
    assert catalog.fresh_calls == [] and catalog.current_calls == []


class FailingFreshCatalog(DialogueCatalog):
    async def get_fresh_product(self, article):
        raise CatalogUnavailable("offline")


async def test_catalog_service_failure_does_not_fabricate_certificate_data() -> None:
    repository = SessionRepository()
    session_id = next(iter(repository.session_ids))
    service = ChatService(repository, FailingFreshCatalog(), UnusedLLM())

    reply = await service.send_message(session_id, ChatMessageCreate(content="Сертификат ABC-123"))

    assert "не удалось получить свежие данные" in reply.assistant_message.content
