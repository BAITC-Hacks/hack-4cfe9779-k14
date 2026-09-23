from typing import Any
from uuid import UUID

from app.config.settings import get_settings
from app.integrations.llm_client import LLMClient, LLMClientError
from app.repositories.attachments import ChatAttachmentRepository
from app.repositories.chat import ChatRepository
from app.schemas.attachment_parsing import AttachmentItemMatch, AttachmentLlmContext, ParsedAttachmentItem
from app.schemas.attachments import AttachmentResult, DocumentType, ExtractedTable
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
from app.services.attachment_parser import AttachmentItemParser
from app.services.errors import ResourceNotFound


class ChatService:
    """Coordinates message persistence, model analysis and server-owned tools."""

    def __init__(
        self,
        repository: ChatRepository,
        catalog: CatalogService,
        llm: LLMClient,
        attachments: ChatAttachmentRepository | None = None,
        attachment_parser: AttachmentItemParser | None = None,
    ) -> None:
        self._repository = repository
        self._catalog = catalog
        self._llm = llm
        self._attachments = attachments
        self._attachment_parser = attachment_parser or AttachmentItemParser()
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
        attachment_results = await self._attachment_results(session_id, payload.attachment_ids)
        attachment_context = [self._llm_context(attachment_id, result) for attachment_id, result in attachment_results]
        user_message = await self._repository.add_message(session_id, ChatRole.USER, payload.content.strip())
        history = await self._repository.history(session_id, limit=self._history_limit)
        try:
            analysis = await self._llm.analyze(
                [ChatMessageView.model_validate(message) for message in history],
                attachment_data=attachment_context,
            )
            reply_text, candidates, current_data = await self._resolve_analysis(analysis)
        except LLMClientError:
            analysis = ChatAnalysis(intent=ChatIntent.UNKNOWN, needs_clarification=True, clarification_question="Уточните, какой товар нужен.")
            reply_text = "Не удалось обработать запрос автоматически. Укажите артикул или характеристики товара."
            candidates = []
            current_data = None

        attachment_items = await self._resolve_attachment_items(attachment_results)
        if attachment_items:
            reply_text = f"{reply_text} {self._attachment_summary(attachment_items)}"

        assistant_message = await self._repository.add_message(
            session_id,
            ChatRole.ASSISTANT,
            reply_text,
            metadata={"analysis": analysis.model_dump(mode="json"), "attachment_ids": [str(value) for value in payload.attachment_ids]},
        )
        return ChatReply(
            session_id=session_id,
            user_message=ChatMessageView.model_validate(user_message),
            assistant_message=ChatMessageView.model_validate(assistant_message),
            analysis=analysis,
            candidates=candidates,
            current_data=current_data,
            attachment_items=attachment_items,
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

    async def _attachment_results(self, session_id: UUID, attachment_ids: list[UUID]) -> list[tuple[UUID, AttachmentResult]]:
        if not attachment_ids:
            return []
        if self._attachments is None:
            raise ResourceNotFound("Attachment processing is unavailable")
        records = await self._attachments.get_for_session(session_id, attachment_ids)
        if len(records) != len(attachment_ids):
            raise ResourceNotFound("One or more attachments were not found in this chat session")
        return [
            (
                record.id,
                AttachmentResult(
                    filename=record.filename,
                    mime_type=record.mime_type,
                    document_type=DocumentType(record.document_type),
                    text=record.extracted_text,
                    tables=[ExtractedTable.model_validate(table) for table in record.tables],
                    warnings=record.warnings,
                    metadata=record.metadata_json,
                ),
            )
            for record in records
        ]

    @staticmethod
    def _llm_context(attachment_id: UUID, result: AttachmentResult) -> AttachmentLlmContext:
        return AttachmentLlmContext(
            attachment_id=attachment_id,
            filename=result.filename,
            document_type=result.document_type,
            text=result.text,
            warnings=result.warnings,
        )

    async def _resolve_attachment_items(self, attachments: list[tuple[UUID, AttachmentResult]]) -> list[AttachmentItemMatch]:
        matches: list[AttachmentItemMatch] = []
        for attachment_id, result in attachments:
            parsed = self._attachment_parser.parse(attachment_id, result)
            for item in parsed:
                matches.append(await self._match_attachment_item(item))
        return matches

    async def _match_attachment_item(self, item: ParsedAttachmentItem) -> AttachmentItemMatch:
        query = item.article or item.product_name
        if not query:
            return AttachmentItemMatch.model_validate(item.model_dump() | {"warnings": [*item.warnings, "item_unrecognized"]})
        search = await self._catalog.search_candidates(query)
        candidates = [candidate.model_dump(mode="json") for candidate in search.candidates]
        warnings = list(item.warnings)
        if not candidates:
            warnings.append("unknown_article" if item.article else "unknown_product")
            return AttachmentItemMatch.model_validate(item.model_dump() | {"candidates": [], "warnings": warnings})
        if len(candidates) > 1:
            warnings.append("product_ambiguous")
            return AttachmentItemMatch.model_validate(item.model_dump() | {"candidates": candidates, "warnings": warnings})
        current = await self._catalog.get_current_availability(candidates[0]["article"])
        return AttachmentItemMatch.model_validate(item.model_dump() | {
            "candidates": candidates, "current_data": current.model_dump(mode="json"), "warnings": warnings,
        })

    @staticmethod
    def _attachment_summary(items: list[AttachmentItemMatch]) -> str:
        unknown = sum(1 for item in items if not item.candidates)
        ambiguous = sum(1 for item in items if "product_ambiguous" in item.warnings)
        quantity_issues = sum(1 for item in items if any(warning.startswith("quantity_") for warning in item.warnings))
        parts = [f"По вложению распознано позиций: {len(items)}."]
        if unknown:
            parts.append(f"Неизвестных позиций: {unknown}.")
        if ambiguous:
            parts.append(f"Неоднозначных совпадений: {ambiguous}.")
        if quantity_issues:
            parts.append(f"Количества требуют уточнения: {quantity_issues}.")
        return " ".join(parts)

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
