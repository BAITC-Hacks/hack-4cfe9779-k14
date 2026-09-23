"""Compatibility-first generation and deterministic ranking of product analogs."""

from __future__ import annotations

from difflib import SequenceMatcher

from app.schemas.analogs import AnalogSearchResult, AnalogSuggestion
from app.schemas.catalog import FreshCatalogProduct
from app.services.catalog import CatalogService
from app.services.compatibility import CompatibilityRules, UnavailableCompatibilityRules
from app.services.errors import ApplicationError, ResourceNotFound


class AnalogService:
    """Never ranks a candidate until the strict compatibility rules accept it."""

    def __init__(self, catalog: CatalogService, rules: CompatibilityRules | None = None) -> None:
        self._catalog = catalog
        self._rules = rules or UnavailableCompatibilityRules()

    async def find_analogs(self, article: str, *, limit: int = 10) -> AnalogSearchResult:
        source = await self._catalog.get_fresh_product(article)
        source_in_stock = self._in_stock(source)
        if source.category is None:
            return AnalogSearchResult(
                source_article=source.article, source_in_stock=source_in_stock,
                rules_source=self._rules.source_label,
            )
        index_candidates = await self._catalog.search_candidates(source.category, limit=100)
        accepted: list[AnalogSuggestion] = []
        for indexed in index_candidates.candidates:
            if indexed.article == source.article:
                continue
            candidate = await self._fresh_candidate(indexed.article)
            if candidate is None or self._in_stock(candidate) is not True:
                continue
            assessment = self._rules.assess(source, candidate)
            if not assessment.compatible:
                continue
            accepted.append(
                AnalogSuggestion(
                    product=candidate,
                    score=self._rank(source, candidate, len(assessment.explanation.matches)),
                    explanation=assessment.explanation,
                )
            )
        accepted.sort(key=lambda item: (-item.score, item.product.article))
        return AnalogSearchResult(
            source_article=source.article,
            source_in_stock=source_in_stock,
            rules_source=self._rules.source_label,
            candidates=accepted[:limit],
        )

    async def _fresh_candidate(self, article: str) -> FreshCatalogProduct | None:
        try:
            return await self._catalog.get_fresh_product(article)
        except (ResourceNotFound, ApplicationError):
            # A candidate without a fresh card cannot safely be offered.
            return None

    @staticmethod
    def _in_stock(product: FreshCatalogProduct) -> bool | None:
        if product.cached_available is not None:
            return product.cached_available
        if product.cached_stock_by_location is None:
            return None
        return sum(product.cached_stock_by_location.values()) > 0

    @staticmethod
    def _rank(source: FreshCatalogProduct, candidate: FreshCatalogProduct, matching_fields: int) -> float:
        name_similarity = SequenceMatcher(None, source.name.casefold(), candidate.name.casefold()).ratio()
        return round(matching_fields * 100 + name_similarity * 10, 3)
