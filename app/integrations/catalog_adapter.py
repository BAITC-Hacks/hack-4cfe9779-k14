"""Normalized catalog boundary used by indexing, search and dialogue services.

Adapters return only application-owned ``CatalogProductUpsert`` values. They
must never let a partner's JSON envelope cross into routes or services.
"""

from __future__ import annotations

from typing import Protocol

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
    """Safe fallback while a production EKT mapper is unavailable."""

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
    """Do not construct an EKT transport until the partner mapper is approved."""
    return UnavailableCatalogAdapter(
        "EKT response mapper is not implemented because the partner JSON contract is not confirmed"
    )
