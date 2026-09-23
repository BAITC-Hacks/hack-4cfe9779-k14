from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.integrations.llm_client import LLMStructuredOutputError
from app.schemas.chat import ChatAnalysis, ChatIntent, ChatMessageCreate, ChatRole
from app.schemas.catalog import CatalogSearchResponse
from app.services.chat import ChatService

pytestmark = pytest.mark.asyncio


class FakeChatRepository:
    def __init__(self) -> None:
        self.session_id = uuid4()
        self.messages = []

    async def create_session(self):
        return SimpleNamespace(id=self.session_id, created_at=datetime.now(timezone.utc))

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
        items = [message for message in self.messages if message.session_id == session_id]
        return items[-limit:] if limit else items


class FakeCatalogService:
    async def search_candidates(self, query, *, characteristics=None, limit=20):
        return CatalogSearchResponse(candidates=[], match_type="none")

    async def get_current_availability(self, article):
        from app.schemas.catalog import CurrentAvailability

        return CurrentAvailability(
            article=article, price=Decimal("10.00"), stock_by_location={"A": 2}, available=True, current=True,
        )


class MockLLM:
    def __init__(self, analysis=None, error=None):
        self.analysis = analysis
        self.error = error
        self.received_history = None

    async def analyze(self, history):
        self.received_history = history
        if self.error:
            raise self.error
        return self.analysis

    async def aclose(self):
        return None


async def test_message_flow_stores_user_and_assistant_and_uses_llm_analysis() -> None:
    repository = FakeChatRepository()
    llm = MockLLM(ChatAnalysis(intent=ChatIntent.FIND_PRODUCT, product_name="cable"))
    service = ChatService(repository, FakeCatalogService(), llm)

    reply = await service.send_message(repository.session_id, ChatMessageCreate(content="Find cable"))

    assert [message.role for message in repository.messages] == ["user", "assistant"]
    assert reply.analysis.intent == ChatIntent.FIND_PRODUCT
    assert reply.assistant_message.content.startswith("Подходящих")
    assert len(llm.received_history) == 1


async def test_llm_invalid_output_is_safe_and_does_not_call_cart_logic() -> None:
    repository = FakeChatRepository()
    llm = MockLLM(error=LLMStructuredOutputError("bad output"))
    service = ChatService(repository, FakeCatalogService(), llm)

    reply = await service.send_message(repository.session_id, ChatMessageCreate(content="add 2 A-1"))

    assert reply.analysis.intent == ChatIntent.UNKNOWN
    assert reply.analysis.needs_clarification is True
    assert [message.role for message in repository.messages] == ["user", "assistant"]


async def test_cart_intent_never_mutates_cart() -> None:
    repository = FakeChatRepository()
    llm = MockLLM(ChatAnalysis(intent=ChatIntent.ADD_TO_CART_REQUEST, article="A-1"))
    service = ChatService(repository, FakeCatalogService(), llm)

    reply = await service.send_message(repository.session_id, ChatMessageCreate(content="add A-1"))

    assert "не добавлен" in reply.assistant_message.content
