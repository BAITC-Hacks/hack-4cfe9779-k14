from typing import Any
from uuid import UUID

from app.config.settings import get_settings
from app.integrations.llm_client import LLMClient, LLMClientError
from app.repositories.chat import ChatRepository
from app.schemas.chat import (
    ChatAnalysis,
    ChatHistoryResponse,
    ChatIntent,
    ChatMessageCreate,
    ChatMessageView,
    ChatReply,
    ChatRole,
    ChatSessionCreated,
)
from app.schemas.catalog import CurrentAvailability
from app.services.catalog import CatalogService
from app.services.errors import ResourceNotFound


class ChatService:
    """Coordinates message persistence, model analysis and server-owned tools."""

    def __init__(self, repository: ChatRepository, catalog: CatalogService, llm: LLMClient) -> None:
        self._repository = repository
        self._catalog = catalog
        self._llm = llm
        self._history_limit = get_settings().llm_history_message_limit

    async def create_session(self) -> ChatSessionCreated:
        session = await self._repository.create_session()
        return ChatSessionCreated(id=session.id, created_at=session.created_at)

    async def history(self, session_id: UUID) -> ChatHistoryResponse:
        await self._require_session(session_id)
        messages = await self._repository.history(session_id)
        return ChatHistoryResponse(
            session_id=session_id,
            messages=[ChatMessageView.model_validate(message) for message in messages],
        )

    async def send_message(self, session_id: UUID, payload: ChatMessageCreate) -> ChatReply:
        await self._require_session(session_id)
        user_message = await self._repository.add_message(session_id, ChatRole.USER, payload.content.strip())
        history = await self._repository.history(session_id, limit=self._history_limit)
        try:
            analysis = await self._llm.analyze([ChatMessageView.model_validate(message) for message in history])
            reply_text, candidates, current_data = await self._resolve_analysis(analysis)
        except LLMClientError:
            analysis = ChatAnalysis(intent=ChatIntent.UNKNOWN, needs_clarification=True, clarification_question="Уточните, какой товар нужен.")
            reply_text = "Не удалось обработать запрос автоматически. Укажите артикул или характеристики товара."
            candidates = []
            current_data = None

        assistant_message = await self._repository.add_message(
            session_id,
            ChatRole.ASSISTANT,
            reply_text,
            metadata={"analysis": analysis.model_dump(mode="json")},
        )
        return ChatReply(
            session_id=session_id,
            user_message=ChatMessageView.model_validate(user_message),
            assistant_message=ChatMessageView.model_validate(assistant_message),
            analysis=analysis,
            candidates=candidates,
            current_data=current_data,
        )

    async def _resolve_analysis(self, analysis: ChatAnalysis) -> tuple[str, list[dict[str, Any]], dict[str, Any] | None]:
        if analysis.needs_clarification:
            return analysis.clarification_question or "Уточните параметры товара.", [], None

        if analysis.intent in (ChatIntent.CHECK_PRICE, ChatIntent.CHECK_STOCK):
            if not analysis.article:
                return "Укажите артикул, чтобы проверить актуальную цену или остаток.", [], None
            current = await self._catalog.get_current_availability(analysis.article)
            return self._current_reply(analysis.intent, current), [], current.model_dump(mode="json")

        query = analysis.article or analysis.product_name
        result = await self._catalog.search_candidates(
            query,
            characteristics=analysis.search_parameters.characteristics or None,
        )
        candidates = [candidate.model_dump(mode="json") for candidate in result.candidates]
        if analysis.intent == ChatIntent.ADD_TO_CART_REQUEST:
            return "Товар не добавлен. Для корзины требуется отдельное серверное предложение и явное подтверждение.", candidates, None
        if not candidates:
            return "Подходящих товаров в локальном каталоге не найдено. Уточните артикул или характеристики.", [], None
        return f"Найдено вариантов: {len(candidates)}.", candidates, None

    @staticmethod
    def _current_reply(intent: ChatIntent, current: CurrentAvailability) -> str:
        if not current.current:
            return "Сейчас не удалось подтвердить актуальные данные у поставщика."
        if intent == ChatIntent.CHECK_PRICE:
            return "Актуальная цена получена у поставщика." if current.price is not None else "Поставщик не вернул актуальную цену."
        return "Актуальный остаток получен у поставщика." if current.stock_by_location is not None else "Поставщик не вернул актуальный остаток."

    async def _require_session(self, session_id: UUID) -> None:
        if await self._repository.get_session(session_id) is None:
            raise ResourceNotFound("Chat session was not found")
