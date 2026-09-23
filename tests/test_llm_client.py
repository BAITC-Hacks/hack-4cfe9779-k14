import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest

from app.config.settings import get_settings
from app.integrations.llm_client import LLMStructuredOutputError, OpenAICompatibleLLMClient
from app.schemas.chat import ChatIntent, ChatMessageView, ChatRole

pytestmark = pytest.mark.asyncio


def configure_llm(monkeypatch: pytest.MonkeyPatch, *, history_limit: int = 2) -> None:
    monkeypatch.setenv("LLM_API_URL", "https://llm.invalid/v1/chat/completions")
    monkeypatch.setenv("LLM_API_KEY", "mock-key")
    monkeypatch.setenv("LLM_MODEL", "mock-model")
    monkeypatch.setenv("LLM_HISTORY_MESSAGE_LIMIT", str(history_limit))
    get_settings.cache_clear()


def message(content: str, role: ChatRole = ChatRole.USER) -> ChatMessageView:
    return ChatMessageView(id=uuid4(), role=role, content=content, created_at=datetime.now(timezone.utc))


async def test_llm_sends_bounded_history_and_validates_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_llm(monkeypatch, history_limit=2)
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        output = {"intent": "find_product", "article": "A-1", "search_parameters": {"characteristics": {"cores": 3}}}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(output)}}]})

    async with OpenAICompatibleLLMClient(transport=httpx.MockTransport(handler)) as client:
        result = await client.analyze([message("old"), message("middle"), message("latest")])

    assert result.intent == ChatIntent.FIND_PRODUCT
    assert result.article == "A-1"
    assert [item["content"] for item in captured["messages"][1:]] == ["middle", "latest"]
    assert captured["response_format"]["json_schema"]["strict"] is True
    assert captured["model"] == "mock-model"


async def test_llm_rejects_invalid_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_llm(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "{not valid json"}}]})

    async with OpenAICompatibleLLMClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LLMStructuredOutputError):
            await client.analyze([message("find cable")])
