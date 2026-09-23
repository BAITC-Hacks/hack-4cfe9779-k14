from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence
from uuid import UUID

from app.config.settings import get_settings
from app.integrations.llm_client import LLMClient, LLMClientError
from app.repositories.attachments import ChatAttachmentRepository
from app.repositories.chat import ChatRepository
from app.schemas.attachment_parsing import AttachmentItemMatch, AttachmentLlmContext, ParsedAttachmentItem
from app.schemas.attachments import AttachmentResult, DocumentType, ExtractedTable
from app.schemas.catalog import CurrentAvailability, FreshCatalogProduct
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
from app.schemas.purchase_conditions import PurchaseConditions
from app.services.attachment_parser import AttachmentItemParser
from app.services.catalog import CatalogService
from app.services.dialogue_router import DeterministicDialogueRouter, DialogueContext
from app.services.errors import ApplicationError, ResourceNotFound
from app.services.purchase_conditions import DemoPurchaseConditionsProvider, PurchaseConditionsProvider


@dataclass
class DialogueResolution:
    text: str
    candidates: list[dict[str, Any]]
    current_data: dict[str, Any] | None
    selected_article: str | None
    purchase_conditions: PurchaseConditions | None = None


class ChatService:
    """Session-scoped, grounded dialogue orchestration over server-owned services."""

    def __init__(
        self,
        repository: ChatRepository,
        catalog: CatalogService,
        llm: LLMClient,
        attachments: ChatAttachmentRepository | None = None,
        attachment_parser: AttachmentItemParser | None = None,
        router: DeterministicDialogueRouter | None = None,
        purchase_conditions: PurchaseConditionsProvider | None = None,
    ) -> None:
        self._repository = repository
        self._catalog = catalog
        self._llm = llm
        self._attachments = attachments
        self._attachment_parser = attachment_parser or AttachmentItemParser()
        self._router = router or DeterministicDialogueRouter()
        self._purchase_conditions = purchase_conditions or DemoPurchaseConditionsProvider()
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
        previous_messages = await self._repository.history(session_id, limit=self._history_limit)
        context = self._context_from_history(previous_messages)
        attachment_results = await self._attachment_results(session_id, payload.attachment_ids)
        user_message = await self._repository.add_message(session_id, ChatRole.USER, payload.content.strip())
        history = await self._repository.history(session_id, limit=self._history_limit)
        analysis = await self._analyze(payload.content, history, attachment_results, context)
        resolution = await self._resolve_analysis(analysis, context)

        attachment_items = await self._resolve_attachment_items(attachment_results)
        if attachment_items:
            resolution.text = f"{resolution.text} {self._attachment_summary(attachment_items)}"
        attachment_notice = self._attachment_notice(attachment_results)
        if attachment_notice:
            resolution.text = f"{resolution.text} {attachment_notice}"

        assistant_message = await self._repository.add_message(
            session_id,
            ChatRole.ASSISTANT,
            resolution.text,
            metadata={
                "analysis": analysis.model_dump(mode="json"),
                "attachment_ids": [str(value) for value in payload.attachment_ids],
                "dialogue_context": {"selected_article": resolution.selected_article},
            },
        )
        return ChatReply(
            session_id=session_id,
            user_message=ChatMessageView.model_validate(user_message),
            assistant_message=ChatMessageView.model_validate(assistant_message),
            analysis=analysis,
            candidates=resolution.candidates,
            current_data=resolution.current_data,
            attachment_items=attachment_items,
            purchase_conditions=resolution.purchase_conditions,
        )

    async def _analyze(
        self,
        content: str,
        history: Sequence[Any],
        attachments: list[tuple[UUID, AttachmentResult]],
        context: DialogueContext,
    ) -> ChatAnalysis:
        # Attachments require the existing bounded extraction/LLM parsing path;
        # deterministic routing resumes after parsed item handling.
        deterministic = None if attachments else self._router.route(content, context)
        if deterministic is not None:
            return deterministic
        attachment_context = [self._llm_context(attachment_id, result) for attachment_id, result in attachments]
        try:
            analysis = await self._llm.analyze(
                [ChatMessageView.model_validate(message) for message in history], attachment_data=attachment_context,
            )
        except LLMClientError:
            return ChatAnalysis(
                intent=ChatIntent.UNKNOWN,
                needs_clarification=True,
                clarification_question="Не удалось обработать запрос автоматически. Укажите артикул или характеристики товара.",
            )
        if context.selected_article and analysis.article is None and analysis.intent in self._product_intents():
            return analysis.model_copy(update={"article": context.selected_article})
        return analysis

    async def _resolve_analysis(self, analysis: ChatAnalysis, context: DialogueContext) -> DialogueResolution:
        selected_article = context.selected_article
        if analysis.needs_clarification:
            return DialogueResolution(
                analysis.clarification_question or "Уточните параметры товара.", [], None, selected_article
            )
        if analysis.intent == ChatIntent.PURCHASE_CONDITIONS:
            conditions = self._purchase_conditions.get_conditions()
            return DialogueResolution(self._conditions_reply(conditions), [], None, selected_article, conditions)
        if analysis.intent == ChatIntent.ADD_TO_CART_REQUEST:
            return DialogueResolution(
                "Товар не добавлен. Для корзины требуется отдельное серверное предложение и явное подтверждение.",
                [], None, selected_article,
            )
        if analysis.intent in (ChatIntent.CHECK_PRICE, ChatIntent.CHECK_STOCK, ChatIntent.CHECK_AVAILABILITY):
            if not analysis.article:
                return DialogueResolution("Укажите артикул товара для проверки актуальных данных.", [], None, selected_article)
            current = await self._catalog.get_current_availability(analysis.article)
            return DialogueResolution(
                self._current_reply(analysis.intent, current), [], current.model_dump(mode="json"),
                analysis.article if current.current else selected_article,
            )
        if analysis.intent in (ChatIntent.CHECK_CERTIFICATES, ChatIntent.PRODUCT_CHARACTERISTICS):
            if not analysis.article:
                return DialogueResolution("Укажите артикул товара.", [], None, selected_article)
            product, error = await self._fresh_product(analysis.article)
            if error:
                return DialogueResolution(error, [], None, selected_article)
            assert product is not None
            text = self._certificates_reply(product) if analysis.intent == ChatIntent.CHECK_CERTIFICATES else self._characteristics_reply(product)
            return DialogueResolution(text, [], product.model_dump(mode="json"), product.article)
        if analysis.intent == ChatIntent.FOLLOW_UP:
            return DialogueResolution(
                "Уточните, что именно хотите узнать: характеристики, наличие, сертификаты или цену.", [], None, selected_article
            )
        if analysis.intent in (ChatIntent.FIND_PRODUCT, ChatIntent.SEARCH_BY_REQUIREMENTS):
            query = analysis.article or analysis.product_name
            if not query:
                return DialogueResolution("Укажите артикул, название или требования к товару.", [], None, selected_article)
            result = await self._catalog.search_candidates(
                query, characteristics=analysis.search_parameters.characteristics or None,
            )
            candidates = [candidate.model_dump(mode="json") for candidate in result.candidates]
            if not candidates:
                return DialogueResolution(
                    "Подходящих товаров в каталоге не найдено. Уточните артикул или характеристики.", [], None, selected_article,
                )
            if len(candidates) > 1:
                choices = "; ".join(f"{item['name']} ({item['article']})" for item in candidates[:3])
                return DialogueResolution(
                    f"Найдено несколько вариантов: {choices}. Укажите точный артикул нужного товара.",
                    candidates, None, None,
                )
            product = candidates[0]
            return DialogueResolution(
                f"Найден товар: {product['name']} ({product['article']}). Что именно хотите узнать?",
                candidates, None, product["article"],
            )
        return DialogueResolution(
            "Я могу помочь найти товар, показать характеристики, наличие, сертификаты или условия покупки. Уточните запрос.",
            [], None, selected_article,
        )

    async def _fresh_product(self, article: str) -> tuple[FreshCatalogProduct | None, str | None]:
        try:
            return await self._catalog.get_fresh_product(article), None
        except ResourceNotFound:
            return None, f"Товар с артикулом {article} не найден."
        except ApplicationError:
            return None, "Сейчас не удалось получить свежие данные о товаре."

    @staticmethod
    def _product_intents() -> tuple[ChatIntent, ...]:
        return (
            ChatIntent.CHECK_PRICE, ChatIntent.CHECK_STOCK, ChatIntent.CHECK_AVAILABILITY,
            ChatIntent.CHECK_CERTIFICATES, ChatIntent.PRODUCT_CHARACTERISTICS,
        )

    @staticmethod
    def _context_from_history(messages: Sequence[Any]) -> DialogueContext:
        for message in reversed(messages):
            role = getattr(message, "role", None)
            if getattr(role, "value", role) != ChatRole.ASSISTANT.value:
                continue
            metadata = getattr(message, "metadata_json", {}) or {}
            dialogue_context = metadata.get("dialogue_context") if isinstance(metadata, dict) else None
            if isinstance(dialogue_context, dict) and "selected_article" in dialogue_context:
                selected = dialogue_context["selected_article"]
                return DialogueContext(selected_article=selected if isinstance(selected, str) else None)
        return DialogueContext()

    @staticmethod
    def _conditions_reply(conditions: PurchaseConditions) -> str:
        if conditions.is_demo:
            return conditions.notice or "DEMO: условия покупки требуют подтверждения."
        parts = [f"Источник условий: {conditions.source_label}."]
        if conditions.payment_methods is not None:
            parts.append(f"Оплата: {', '.join(conditions.payment_methods) or 'не указана'}.")
        if conditions.delivery is not None:
            parts.append(f"Доставка: {conditions.delivery}.")
        if conditions.minimum_order is not None:
            parts.append(f"Минимальная партия: {conditions.minimum_order}.")
        if conditions.notice:
            parts.append(conditions.notice)
        return " ".join(parts)

    @staticmethod
    def _certificates_reply(product: FreshCatalogProduct) -> str:
        presence = product.source_field_presence.get("certificates")
        if presence is False or product.certificates is None:
            return "Источник не предоставил данные о сертификатах для этого товара."
        if not product.certificates:
            return "Источник указал, что сертификаты для этого товара отсутствуют."
        values = "; ".join(
            ", ".join(f"{key}: {value}" for key, value in certificate.items())
            for certificate in product.certificates
        )
        return f"Сертификаты из свежей карточки: {values}."

    @staticmethod
    def _characteristics_reply(product: FreshCatalogProduct) -> str:
        presence = product.source_field_presence.get("characteristics")
        if presence is False or product.characteristics is None:
            return "Источник не предоставил характеристики для этого товара."
        if not product.characteristics:
            return "Источник указал пустой набор характеристик для этого товара."
        values = "; ".join(f"{key}: {value}" for key, value in product.characteristics.items())
        return f"Характеристики из свежей карточки: {values}."

    @staticmethod
    def _current_reply(intent: ChatIntent, current: CurrentAvailability) -> str:
        if not current.current:
            if current.reason == "unknown_sku":
                return f"Товар с артикулом {current.article} не найден."
            return "Сейчас не удалось подтвердить актуальные данные у поставщика."
        if intent == ChatIntent.CHECK_PRICE:
            return (
                f"Актуальная цена из свежей карточки: {current.price}."
                if current.price is not None else "Поставщик не предоставил актуальную цену."
            )
        if current.stock_by_location is None:
            return "Поставщик не предоставил актуальные остатки по складам."
        stock = "; ".join(f"{location}: {quantity}" for location, quantity in current.stock_by_location.items())
        if current.available is None:
            return f"Актуальные остатки по складам: {stock}. Доступность отдельно не предоставлена."
        status = "доступен" if current.available else "нет в наличии"
        return f"Товар {status}. Актуальные остатки по складам: {stock}."

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
                    filename=record.filename, mime_type=record.mime_type, document_type=DocumentType(record.document_type),
                    text=record.extracted_text, tables=[ExtractedTable.model_validate(table) for table in record.tables],
                    warnings=record.warnings, metadata=record.metadata_json,
                ),
            )
            for record in records
        ]

    @staticmethod
    def _llm_context(attachment_id: UUID, result: AttachmentResult) -> AttachmentLlmContext:
        return AttachmentLlmContext(
            attachment_id=attachment_id, filename=result.filename, document_type=result.document_type,
            text=result.text, warnings=result.warnings,
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
    def _attachment_notice(attachments: list[tuple[UUID, AttachmentResult]]) -> str:
        warnings = {warning for _, result in attachments for warning in result.warnings}
        notices: list[str] = []
        if "ocr_failed" in warnings:
            notices.append("OCR не смог распознать изображение; загрузите более чёткий файл или введите позиции текстом.")
        elif "empty_document" in warnings:
            notices.append("В документе не удалось распознать текст; проверьте файл или загрузите более чёткий скан.")
        if any(warning == "pdf_may_require_ocr" or warning == "pdf_page_text_unavailable" or warning.startswith("xlsx_sheet_truncated:") for warning in warnings):
            notices.append("Часть содержимого могла быть распознана не полностью; проверьте позиции перед продолжением.")
        return " ".join(notices)

    async def _require_session(self, session_id: UUID) -> None:
        if await self._repository.get_session(session_id) is None:
            raise ResourceNotFound("Chat session was not found")
