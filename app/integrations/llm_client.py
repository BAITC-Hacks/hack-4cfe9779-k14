"""Provider-neutral LLM interface and an OpenAI-compatible HTTP implementation."""

from __future__ import annotations

import logging
from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from app.config.settings import get_settings
from app.schemas.chat import ChatAnalysis, ChatMessageView

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    code = "llm_error"


class LLMConfigurationError(LLMClientError):
    code = "llm_configuration_error"


class LLMUnavailableError(LLMClientError):
    code = "llm_unavailable"


class LLMStructuredOutputError(LLMClientError):
    code = "llm_structured_output_error"


class LLMClient(Protocol):
    async def analyze(self, history: list[ChatMessageView]) -> ChatAnalysis: ...

    async def aclose(self) -> None: ...


class UnavailableLLMClient:
    """Safe placeholder used when server-side LLM configuration is missing."""

    async def analyze(self, history: list[ChatMessageView]) -> ChatAnalysis:
        del history
        raise LLMUnavailableError("Language model is not configured")

    async def aclose(self) -> None:
        return None


class OpenAICompatibleLLMClient:
    """Uses an OpenAI-compatible JSON-schema response format over plain HTTP.

    The only provider-specific contract in the application lives in this class.
    It does not expose tools, database credentials, EKT credentials, or cart APIs
    to the model.
    """

    SYSTEM_PROMPT = """You classify product-chat messages. Return JSON matching the supplied schema.
Extract intent, article, product name, quantity, search parameters, and whether clarification is needed.
You cannot access tools, databases, EKT, a cart, prices, or stock. Never claim an item was added to a cart.
For a request to add an item, use add_to_cart_request; the server will decide any action."""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        settings = get_settings()
        if not settings.llm_api_url or not settings.llm_api_key or not settings.llm_model:
            raise LLMConfigurationError("Set LLM_API_URL, LLM_API_KEY, and LLM_MODEL on the server")
        if not settings.llm_api_url.startswith(("https://", "http://")):
            raise LLMConfigurationError("LLM_API_URL must be an absolute HTTP(S) URL")
        self._history_limit = settings.llm_history_message_limit
        if not 1 <= self._history_limit <= 100:
            raise LLMConfigurationError("LLM_HISTORY_MESSAGE_LIMIT must be between 1 and 100")
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout=settings.llm_timeout_seconds, connect=min(5.0, settings.llm_timeout_seconds)),
            headers={"Authorization": f"Bearer {settings.llm_api_key.get_secret_value()}"},
            follow_redirects=False,
            transport=transport,
        )
        self._url = settings.llm_api_url
        self._model = settings.llm_model
        self._temperature = settings.llm_temperature

    async def __aenter__(self) -> "OpenAICompatibleLLMClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def analyze(self, history: list[ChatMessageView]) -> ChatAnalysis:
        bounded_history = history[-self._history_limit :]
        payload = {
            "model": self._model,
            "temperature": self._temperature,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                *[{"role": message.role.value, "content": message.content} for message in bounded_history],
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "chat_analysis",
                    "strict": True,
                    "schema": ChatAnalysis.model_json_schema(),
                },
            },
        }
        try:
            response = await self._client.post(self._url, json=payload)
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError) as exc:
            logger.warning(
                "llm_request_failed",
                extra={"event": "llm_request_failed", "error_type": type(exc).__name__},
            )
            raise LLMUnavailableError("Language model is temporarily unavailable") from None
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("LLM content must be a JSON string")
            return ChatAnalysis.model_validate_json(content)
        except (KeyError, IndexError, TypeError, ValueError, ValidationError):
            logger.warning("llm_invalid_structured_output", extra={"event": "llm_invalid_structured_output"})
            raise LLMStructuredOutputError("Language model returned an invalid structured response") from None
