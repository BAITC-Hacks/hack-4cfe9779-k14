"""Normalized catalog boundary used by indexing, search and dialogue services.

Adapters return only application-owned ``CatalogProductUpsert`` values. They
must never let a partner's JSON envelope cross into routes or services.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol, Sequence

from pydantic import ValidationError

from app.integrations.ekt_client import (
    EktAuthenticationError,
    EktClient,
    EktClientError,
    EktInvalidJsonError,
    EktProduct,
    EktProductNotFoundError,
    EktResponseFormatError,
    EktTimeoutError,
)
from app.config.settings import get_settings
from app.schemas.catalog import CatalogPage, CatalogProductUpsert


class CatalogAdapterError(Exception):
    """Sanitized adapter failure; partner response bodies are never retained."""

    code = "catalog_adapter_error"


class CatalogAdapterNotFoundError(CatalogAdapterError):
    code = "catalog_not_found"


class CatalogAdapterTimeoutError(CatalogAdapterError):
    code = "catalog_timeout"


class CatalogAdapterAuthenticationError(CatalogAdapterError):
    code = "catalog_authentication_error"


class CatalogAdapterMalformedResponseError(CatalogAdapterError):
    code = "catalog_malformed_response"


class CatalogAdapterUnavailableError(CatalogAdapterError):
    code = "catalog_unavailable"


class CatalogAdapter(Protocol):
    """Single catalog contract, independent of the selected data source."""

    async def get_product_by_article(self, article: str) -> CatalogProductUpsert: ...

    async def get_product_details(self, external_id: str) -> CatalogProductUpsert: ...

    async def get_products_page(self, page: int = 1, *, page_size: int = 50) -> CatalogPage: ...

    async def aclose(self) -> None: ...


class MockCatalogAdapter:
    """Read-only adapter over the explicit synthetic dataset used in development."""

    def __init__(self, products: Sequence[CatalogProductUpsert]) -> None:
        self._products = list(products)

    @classmethod
    def from_file(cls, path: Path) -> "MockCatalogAdapter":
        try:
            dataset = json.loads(path.read_text(encoding="utf-8"))
            rows = dataset["products"]
            if not isinstance(rows, list):
                raise TypeError("products must be a list")
            products = [cls._normalize_mock_row(row) for row in rows]
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
            raise CatalogAdapterMalformedResponseError("Mock catalog data is invalid") from exc
        return cls(products)

    @staticmethod
    def _normalize_mock_row(row: Any) -> CatalogProductUpsert:
        if not isinstance(row, dict):
            raise TypeError("product row must be an object")
        presence = {
            field: field in row
            for field in CatalogProductUpsert.model_fields
            if field != "source_field_presence"
        }
        return CatalogProductUpsert.model_validate(row).model_copy(
            update={"source_field_presence": presence}
        )

    async def get_product_by_article(self, article: str) -> CatalogProductUpsert:
        normalized = article.strip().casefold()
        if not normalized:
            raise CatalogAdapterNotFoundError("Product article was not found")
        for product in self._products:
            if product.article.casefold() == normalized:
                return product
        raise CatalogAdapterNotFoundError("Product article was not found")

    async def get_product_details(self, external_id: str) -> CatalogProductUpsert:
        normalized = external_id.strip()
        for product in self._products:
            if product.external_id == normalized:
                return product
        raise CatalogAdapterNotFoundError("Product details were not found")

    async def get_products_page(self, page: int = 1, *, page_size: int = 50) -> CatalogPage:
        if page < 1 or page_size < 1:
            raise ValueError("page and page_size must be greater than zero")
        start = (page - 1) * page_size
        products = self._products[start : start + page_size]
        return CatalogPage(page=page, products=products, has_more=start + page_size < len(self._products))

    async def aclose(self) -> None:
        return None


class EktCatalogAdapter:
    """Adapter over only the documented EKT GET operations.

    A real ``EktResponseMapper`` remains mandatory before this adapter is wired
    into production. ``EktClient`` owns Basic Auth, timeouts and safe retries.
    """

    def __init__(self, client: EktClient) -> None:
        self._client = client

    async def get_product_by_article(self, article: str) -> CatalogProductUpsert:
        try:
            return self._normalize(await self._client.get_current_product_by_article(article))
        except EktClientError as exc:
            raise self._translate_error(exc) from None

    async def get_product_details(self, external_id: str) -> CatalogProductUpsert:
        try:
            return self._normalize(await self._client.get_product_details(external_id))
        except EktClientError as exc:
            raise self._translate_error(exc) from None

    async def get_products_page(self, page: int = 1, *, page_size: int = 50) -> CatalogPage:
        del page_size  # EKT does not document a page-size parameter.
        try:
            products = [self._normalize(product) for product in await self._client.get_products_page(page)]
        except EktClientError as exc:
            raise self._translate_error(exc) from None
        # Termination metadata is unknown: a non-empty page may be followed by
        # one final empty request, exactly as documented by EktClient.
        return CatalogPage(page=page, products=products, has_more=bool(products))

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _normalize(product: EktProduct) -> CatalogProductUpsert:
        presence = dict(product.source_field_presence)
        presence.update({"article": True, "external_id": True, "name": True})
        return CatalogProductUpsert(
            article=product.article,
            external_id=product.id,
            name=product.name,
            description=product.description,
            brand=product.brand,
            category=product.category,
            characteristics=product.attributes,
            cached_price=product.price,
            cached_stock_by_location=product.stock_by_location,
            # EKT has not documented an explicit availability field. Do not
            # infer it from stock here; callers can calculate when appropriate.
            cached_available=None,
            certificates=product.certificates,
            source_fields=product.source_fields,
            source_field_presence=presence,
        )

    @staticmethod
    def _translate_error(error: EktClientError) -> CatalogAdapterError:
        if isinstance(error, EktProductNotFoundError):
            return CatalogAdapterNotFoundError("Product was not found")
        if isinstance(error, EktTimeoutError):
            return CatalogAdapterTimeoutError("Catalog request timed out")
        if isinstance(error, EktAuthenticationError):
            return CatalogAdapterAuthenticationError("Catalog authentication failed")
        if isinstance(error, (EktInvalidJsonError, EktResponseFormatError)):
            return CatalogAdapterMalformedResponseError("Catalog response has an unsupported format")
        return CatalogAdapterUnavailableError("Catalog is unavailable")


class UnavailableCatalogAdapter:
    """Explicit non-mock fallback while a production EKT mapper is unavailable."""

    def __init__(self, reason: str = "Catalog adapter is not configured") -> None:
        self._reason = reason

    async def get_product_by_article(self, article: str) -> CatalogProductUpsert:
        del article
        raise CatalogAdapterUnavailableError(self._reason)

    async def get_product_details(self, external_id: str) -> CatalogProductUpsert:
        del external_id
        raise CatalogAdapterUnavailableError(self._reason)

    async def get_products_page(self, page: int = 1, *, page_size: int = 50) -> CatalogPage:
        del page, page_size
        raise CatalogAdapterUnavailableError(self._reason)

    async def aclose(self) -> None:
        return None


def build_catalog_adapter() -> CatalogAdapter:
    """Build the configured adapter without guessing an EKT response mapper."""
    settings = get_settings()
    if settings.catalog_adapter_mode == "mock":
        path = (
            Path(settings.catalog_mock_data_path)
            if settings.catalog_mock_data_path
            else Path(__file__).parents[2] / "testdata" / "mock_catalog.json"
        )
        return MockCatalogAdapter.from_file(path)
    if settings.catalog_adapter_mode == "ekt":
        return UnavailableCatalogAdapter(
            "EKT response mapper is not implemented because the partner JSON contract is not confirmed"
        )
    return UnavailableCatalogAdapter("CATALOG_ADAPTER_MODE must be mock or ekt")
