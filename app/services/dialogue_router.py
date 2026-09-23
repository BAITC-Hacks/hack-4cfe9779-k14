"""Deterministic intent routing for catalog requests and contextual follow-ups."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.chat import ChatAnalysis, ChatIntent


ARTICLE_PATTERN = re.compile(r"(?<![\w-])([A-Za-z0-9]+(?:[-_/][A-Za-z0-9]+)+)(?![\w-])")


@dataclass(frozen=True)
class DialogueContext:
    selected_article: str | None = None


class DeterministicDialogueRouter:
    """Routes unambiguous product questions without asking an LLM for facts."""

    def route(self, content: str, context: DialogueContext) -> ChatAnalysis | None:
        normalized = content.strip().casefold()
        article = self._article(content) or context.selected_article

        # Existing LLM classification handles cart-like phrasing; the router
        # deliberately leaves it untouched because it never mutates a cart.
        if normalized.startswith("add ") or "добав" in normalized:
            return None

        if self._contains(normalized, "оплат", "достав", "минимальн", "услови", "самовывоз"):
            return ChatAnalysis(intent=ChatIntent.PURCHASE_CONDITIONS)
        if self._contains(normalized, "сертифик"):
            return self._product_question(ChatIntent.CHECK_CERTIFICATES, article, "Укажите артикул товара, чтобы проверить сертификаты.")
        if self._contains(normalized, "налич", "остат", "сколько", "есть в наличии"):
            return self._product_question(ChatIntent.CHECK_AVAILABILITY, article, "Укажите артикул товара, чтобы проверить наличие.")
        if self._contains(normalized, "характерист", "параметр", "сечени", "жил"):
            return self._product_question(ChatIntent.PRODUCT_CHARACTERISTICS, article, "Укажите артикул товара, чтобы показать характеристики.")
        if self._contains(normalized, "цен", "стоимост"):
            return self._product_question(ChatIntent.CHECK_PRICE, article, "Укажите артикул товара, чтобы проверить цену.")
        if self._article(content):
            return ChatAnalysis(intent=ChatIntent.FIND_PRODUCT, article=self._article(content))
        if self._contains(normalized, "найди", "покажи", "ищу", "нужен", "подбери"):
            return ChatAnalysis(intent=ChatIntent.SEARCH_BY_REQUIREMENTS, product_name=content.strip())
        if context.selected_article and self._contains(normalized, "него", "нему", "этот", "этого", "его"):
            return ChatAnalysis(intent=ChatIntent.FOLLOW_UP, article=context.selected_article, needs_clarification=True, clarification_question="Уточните, что именно хотите узнать об этом товаре: характеристики, наличие, сертификаты или цену.")
        return None

    @staticmethod
    def _article(content: str) -> str | None:
        match = ARTICLE_PATTERN.search(content)
        return match.group(1) if match else None

    @staticmethod
    def _contains(content: str, *fragments: str) -> bool:
        return any(fragment in content for fragment in fragments)

    @staticmethod
    def _product_question(intent: ChatIntent, article: str | None, clarification: str) -> ChatAnalysis:
        if article:
            return ChatAnalysis(intent=intent, article=article)
        return ChatAnalysis(intent=intent, needs_clarification=True, clarification_question=clarification)
