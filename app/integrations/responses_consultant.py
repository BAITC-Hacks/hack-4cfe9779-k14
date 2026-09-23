"""Async bridge from the shared CLI model schemas to server-owned catalog logic."""
import json
import re

from openai import AsyncOpenAI, APIError
from pydantic import HttpUrl, ValidationError

from hack_4cfe9779_k14.consultant import MODEL, Query, Draft, QUERY_INSTRUCTIONS, ANSWER_INSTRUCTIONS
from app.config.settings import get_settings
from app.integrations.llm_client import LLMConfigurationError, LLMStructuredOutputError, LLMUnavailableError
from app.schemas.chat import ChatAnalysis, ChatIntent, SearchParameters


class ResponsesConsultant:
    def __init__(self, client=None):
        settings = get_settings()
        if client is None and not settings.openai_api_key:
            raise LLMConfigurationError("OPENAI_API_KEY is not configured")
        self.client = client or AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            base_url="https://api.openai.com/v1", timeout=25, max_retries=0,
        )
        self.model = settings.openai_model or MODEL
        self.history_limit = settings.llm_history_message_limit

    async def aclose(self):
        await self.client.close()

    async def _parse(self, schema, instructions, payload):
        content = json.dumps(payload, ensure_ascii=False, default=str)
        if len(content) > 120000:
            raise LLMStructuredOutputError("Model context exceeds limit")
        try:
            response = await self.client.responses.parse(
                model=self.model, instructions=instructions,
                input=[{"role": "user", "content": content}], text_format=schema,
                reasoning={"effort": "low"}, max_output_tokens=2000, store=False,
            )
        except APIError:
            raise LLMUnavailableError("Model request failed; check server OpenAI configuration and quota") from None
        except (ValueError, ValidationError):
            raise LLMStructuredOutputError("Invalid model output") from None
        if response.status != "completed" or response.output_parsed is None:
            raise LLMStructuredOutputError("Model response was refused or incomplete")
        return response.output_parsed

    async def analyze(self, history, attachment_data=None):
        turns = [{"role": message.role.value, "content": message.content} for message in history[-self.history_limit:]]
        if attachment_data:
            raise LLMStructuredOutputError("Attachments must be processed locally")
        query = await self._parse(Query, QUERY_INSTRUCTIONS,
                                  {"message": turns[-1]["content"], "history": turns[:-1], "vocabulary": {}})
        intent = {
            "availability": ChatIntent.CHECK_AVAILABILITY,
            "alternatives": ChatIntent.FIND_ANALOG,
            "purchase_terms": ChatIntent.PURCHASE_CONDITIONS,
            "cart_request": ChatIntent.ADD_TO_CART_REQUEST,
            "clarification": ChatIntent.UNKNOWN,
            "price": ChatIntent.CHECK_PRICE,
            "certificates": ChatIntent.CHECK_CERTIFICATES,
        }.get(query.intent, ChatIntent.PRODUCT_CHARACTERISTICS if query.sku else ChatIntent.SEARCH_BY_REQUIREMENTS)
        quantity = query.quantity
        clarification = query.clarification
        if quantity is not None and (not quantity.is_integer() or quantity > 10000):
            quantity = None
            clarification = "В прототипе укажите целое количество от 1 до 10000."
        return ChatAnalysis(
            intent=intent, article=query.sku, product_name=query.query or None,
            quantity=int(quantity) if quantity is not None else None,
            search_parameters=SearchParameters(characteristics={a.name: a.value for a in query.attributes}),
            needs_clarification=bool(clarification), clarification_question=clarification,
        )

    async def compose(self, message, facts):
        instructions = ANSWER_INSTRUCTIONS.replace(
            "Цена/наличие — значения снимка с датой источника, а не подтверждение в реальном времени.",
            "Цена/наличие допустимы только из fresh/current данных facts. mode=live означает данные API EKT на момент запроса. Это не резерв товара.",
        )
        draft = await self._parse(Draft, instructions, {"message": message, "facts": facts})
        known = {p["id"] for p in facts["products"]}
        sources = {s["id"] for s in facts["sources"]}
        if not set(draft.product_ids) <= known or not set(draft.source_ids) <= sources:
            raise LLMStructuredOutputError("Model cited unknown sources/products")
        allowed_urls = {str(HttpUrl(s["url"])) for s in facts["sources"] if s.get("url")}
        for url in re.findall(r"https?://[^\s<>\"')\]]+", draft.reply):
            if str(HttpUrl(url.rstrip(".,;"))) not in allowed_urls:
                raise LLMStructuredOutputError("Model cited an ungrounded URL")
        return draft.reply
