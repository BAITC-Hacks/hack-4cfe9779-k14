import logging
from typing import Any, Protocol

from app.integrations.ekt_client import EktClientError, EktProduct
from app.repositories.catalog import CatalogRepository
from app.schemas.catalog import CatalogCandidate, CatalogProductUpsert, CatalogSearchResponse, CurrentAvailability

logger = logging.getLogger(__name__)


class CurrentProductProvider(Protocol):
    async def get_current_product_by_article(self, article: str) -> EktProduct: ...


class CatalogService:
    """Catalog use cases; routes and future chat code never query ORM directly."""

    def __init__(self, repository: CatalogRepository, ekt_client: CurrentProductProvider | None = None) -> None:
        self._repository = repository
        self._ekt_client = ekt_client

    async def save_product(self, payload: CatalogProductUpsert) -> CatalogCandidate:
        return CatalogCandidate.model_validate(await self._repository.upsert(payload))

    async def search_candidates(
        self,
        query: str | None,
        *,
        characteristics: dict[str, Any] | None = None,
        limit: int = 20,
    ) -> CatalogSearchResponse:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        normalized_query = (query or "").strip()
        if not normalized_query and not characteristics:
            return CatalogSearchResponse(candidates=[], match_type="none")

        if normalized_query:
            exact = await self._repository.find_by_article(normalized_query)
            if exact is not None and self._matches_characteristics(exact.characteristics, characteristics):
                return CatalogSearchResponse(
                    candidates=[CatalogCandidate.model_validate(exact)], match_type="exact_article"
                )

        products = await self._repository.full_text_search(
            normalized_query or None, characteristics=characteristics, limit=limit
        )
        return CatalogSearchResponse(
            candidates=[CatalogCandidate.model_validate(product) for product in products],
            match_type="full_text" if products else "none",
        )

    async def get_current_availability(self, article: str) -> CurrentAvailability:
        """Return only EKT-confirmed price/stock; local cache is never a fallback."""
        if self._ekt_client is None:
            return CurrentAvailability(
                article=article, price=None, stock_by_location=None, available=None,
                current=False, reason="ekt_client_not_configured",
            )
        try:
            current = await self._ekt_client.get_current_product_by_article(article)
        except EktClientError as exc:
            logger.warning(
                "catalog_current_data_unavailable",
                extra={"event": "catalog_current_data_unavailable", "article": article, "error_code": exc.code},
            )
            return CurrentAvailability(
                article=article, price=None, stock_by_location=None, available=None,
                current=False, reason="ekt_unavailable",
            )

        stock = current.stock_by_location
        return CurrentAvailability(
            article=current.article,
            price=current.price,
            stock_by_location=stock,
            available=sum(stock.values()) > 0 if stock is not None else None,
            current=True,
        )

    @staticmethod
    def _matches_characteristics(
        product_characteristics: dict[str, Any], requested: dict[str, Any] | None,
    ) -> bool:
        return requested is None or all(product_characteristics.get(key) == value for key, value in requested.items())
