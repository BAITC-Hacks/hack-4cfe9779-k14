from __future__ import annotations

import logging
import re
from typing import Any

from app.integrations.catalog_adapter import (
    CatalogAdapter,
    CatalogAdapterAuthenticationError,
    CatalogAdapterError,
    CatalogAdapterMalformedResponseError,
    CatalogAdapterNotFoundError,
    CatalogAdapterTimeoutError,
    EktCatalogAdapter,
)
from app.repositories.catalog import CatalogRepository
from app.schemas.catalog import (
    CatalogCandidate,
    CatalogIndexRefresh,
    CatalogProductUpsert,
    CatalogSearchResponse,
    CurrentAvailability,
    FreshCatalogProduct,
)
from app.services.errors import CatalogAuthenticationFailed, CatalogDataInvalid, CatalogUnavailable, ResourceNotFound

logger = logging.getLogger(__name__)
SKU_QUERY = re.compile(r"^(?=.*\d)[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9._/-]*$")


class CatalogService:
    """Catalog use cases over a local index and a replaceable normalized adapter."""

    def __init__(self, repository: CatalogRepository, adapter: CatalogAdapter | None = None) -> None:
        self._repository = repository
        self._adapter = adapter

    async def save_product(self, payload: CatalogProductUpsert) -> CatalogCandidate:
        return CatalogCandidate.model_validate(await self._repository.upsert(payload))

    async def refresh_index(self, *, max_pages: int = 1000, page_size: int = 50) -> CatalogIndexRefresh:
        if self._adapter is None:
            raise CatalogUnavailable("Catalog adapter is not configured")
        if not 1 <= max_pages <= 1000 or page_size < 1:
            raise ValueError("invalid refresh pagination")
        pages_loaded = 0
        products_loaded = 0
        try:
            for page_number in range(1, max_pages + 1):
                page = await self._adapter.get_products_page(page_number, page_size=page_size)
                pages_loaded += 1
                for product in page.products:
                    await self._repository.upsert(product)
                    products_loaded += 1
                if not page.has_more:
                    return CatalogIndexRefresh(pages_loaded=pages_loaded, products_loaded=products_loaded)
        except CatalogAdapterError as exc:
            raise self._public_adapter_error(exc) from None
        raise CatalogDataInvalid("Catalog pagination limit was reached")

    async def list_products(self, *, limit: int = 100) -> CatalogSearchResponse:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        products = await self._repository.full_text_search(None, limit=limit)
        return CatalogSearchResponse(
            candidates=[CatalogCandidate.model_validate(product) for product in products],
            match_type="catalog",
        )

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
            if self._looks_like_sku(normalized_query):
                return await self._search_remote_exact_sku(normalized_query, characteristics)

        products = await self._repository.full_text_search(
            normalized_query or None, characteristics=characteristics, limit=limit
        )
        return CatalogSearchResponse(
            candidates=[CatalogCandidate.model_validate(product) for product in products],
            match_type="full_text" if products else "none",
        )

    async def _read_product(self, article: str) -> CatalogProductUpsert:
        assert self._adapter is not None
        if isinstance(self._adapter, EktCatalogAdapter):
            indexed = await self._repository.find_by_article(article)
            if indexed is None or not indexed.external_id:
                raise CatalogAdapterNotFoundError("Article is not in the loaded EKT index")
            product = await self._adapter.get_product_details(indexed.external_id)
            if product.article.casefold() != article.casefold() or product.external_id != indexed.external_id:
                raise CatalogAdapterMalformedResponseError("EKT detail does not match indexed product")
            return product
        return await self._adapter.get_product_by_article(article)

    async def load_source_page(self, page: int):
        if self._adapter is None:
            raise CatalogUnavailable("Catalog adapter is not configured")
        try:
            result = await self._adapter.get_products_page(page, page_size=20)
        except CatalogAdapterError as exc:
            raise self._public_adapter_error(exc) from None
        products = [await self.save_product(product) for product in result.products]
        return {"page": result.page, "has_more": result.has_more, "candidates": products}

    async def get_fresh_product(self, article: str, *, persist: bool = True) -> FreshCatalogProduct:
        """Fetch direct adapter details; never substitute indexed cache values.

        Offer confirmation passes ``persist=False`` while it holds its own DB
        transaction: freshness is still obtained from the adapter, but the
        search-index cache is not committed inside that transaction.
        """
        if self._adapter is None:
            raise CatalogUnavailable("Catalog adapter is not configured")
        try:
            product = await self._read_product(article)
        except CatalogAdapterNotFoundError:
            raise ResourceNotFound("Product article was not found") from None
        except CatalogAdapterError as exc:
            raise self._public_adapter_error(exc) from None
        if persist:
            await self._repository.upsert(product)
        return FreshCatalogProduct.model_validate(product.model_dump() | {"fresh": True})

    async def get_current_availability(self, article: str) -> CurrentAvailability:
        """Return only a direct adapter response; indexed values are never fallback data."""
        if self._adapter is None:
            return self._unavailable(article, "catalog_adapter_not_configured")
        try:
            product = await self._read_product(article)
        except CatalogAdapterNotFoundError:
            return self._unavailable(article, "unknown_sku")
        except CatalogAdapterTimeoutError:
            return self._unavailable(article, "catalog_timeout")
        except CatalogAdapterAuthenticationError:
            logger.warning("catalog_current_authentication_failed", extra={"event": "catalog_current_authentication_failed"})
            return self._unavailable(article, "catalog_unavailable")
        except CatalogAdapterError:
            logger.warning("catalog_current_data_unavailable", extra={"event": "catalog_current_data_unavailable"})
            return self._unavailable(article, "catalog_unavailable")

        await self._repository.upsert(product)
        return CurrentAvailability(
            article=product.article,
            price=product.cached_price,
            stock_by_location=product.cached_stock_by_location,
            available=product.cached_available,
            current=True,
        )

    async def _search_remote_exact_sku(
        self, article: str, characteristics: dict[str, Any] | None
    ) -> CatalogSearchResponse:
        if self._adapter is None:
            return CatalogSearchResponse(candidates=[], match_type="none")
        try:
            product = await self._read_product(article)
        except CatalogAdapterNotFoundError:
            # A SKU-like request intentionally does not fall through to fuzzy
            # text search: an unknown article must never become a near match.
            return CatalogSearchResponse(candidates=[], match_type="none")
        except CatalogAdapterError as exc:
            raise self._public_adapter_error(exc) from None
        if not self._matches_characteristics(product.characteristics, characteristics):
            return CatalogSearchResponse(candidates=[], match_type="none")
        candidate = await self.save_product(product)
        return CatalogSearchResponse(candidates=[candidate], match_type="exact_article")

    @staticmethod
    def _looks_like_sku(query: str) -> bool:
        return bool(SKU_QUERY.fullmatch(query))

    @staticmethod
    def _matches_characteristics(
        product_characteristics: dict[str, Any], requested: dict[str, Any] | None,
    ) -> bool:
        return requested is None or all(product_characteristics.get(key) == value for key, value in requested.items())

    @staticmethod
    def _unavailable(article: str, reason: str) -> CurrentAvailability:
        return CurrentAvailability(
            article=article, price=None, stock_by_location=None, available=None, current=False, reason=reason
        )

    @staticmethod
    def _public_adapter_error(error: CatalogAdapterError) -> CatalogUnavailable | CatalogAuthenticationFailed | CatalogDataInvalid:
        if isinstance(error, CatalogAdapterAuthenticationError):
            return CatalogAuthenticationFailed("Catalog source authentication failed")
        if isinstance(error, CatalogAdapterMalformedResponseError):
            return CatalogDataInvalid("Catalog source returned invalid data")
        return CatalogUnavailable("Catalog source is unavailable")
