"""Server-side adapter for the documented subset of the ekt.kz API.

Only endpoint paths recorded in the project brief are used here. The upstream
JSON schema is not documented, so callers must provide an explicit mapper.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

# These paths and query parameters are the only upstream contract currently
# confirmed in project-provided materials. Do not add cart/write routes here
# until the partner documents them.
PRODUCTS_PATH = "products"
PRODUCT_DETAIL_PATH = "products/detail"


class EktClientError(Exception):
    """Base exception for sanitized upstream API failures."""

    code = "ekt_api_error"


class EktConfigurationError(EktClientError):
    code = "ekt_configuration_error"


class EktTimeoutError(EktClientError):
    code = "ekt_timeout"


class EktConnectionError(EktClientError):
    code = "ekt_connection_error"


class EktClientRequestError(EktClientError):
    code = "ekt_client_error"


class EktAuthenticationError(EktClientRequestError):
    code = "ekt_authentication_error"


class EktNotFoundError(EktClientRequestError):
    code = "ekt_not_found"


class EktServerError(EktClientError):
    code = "ekt_server_error"


class EktInvalidJsonError(EktClientError):
    code = "ekt_invalid_json"


class EktResponseFormatError(EktClientError):
    code = "ekt_response_format_error"


class EktProductNotFoundError(EktClientError):
    code = "ekt_product_not_found"


class EktDataUnavailableError(EktClientError):
    code = "ekt_data_unavailable"


class EktProduct(BaseModel):
    """Application-owned product model; never contains upstream JSON shapes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    article: str = Field(min_length=1)
    name: str = Field(min_length=1)
    price: Decimal | None = None
    stock_by_location: dict[str, int] | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class EktPriceCheck(BaseModel):
    article: str
    price: Decimal


class EktStockCheck(BaseModel):
    article: str
    stock_by_location: dict[str, int]

    @property
    def total_quantity(self) -> int:
        return sum(self.stock_by_location.values())


class EktResponseMapper(Protocol):
    """Translate partner-specific JSON into the internal model.

    Implementations must validate the actual response schema documented by EKT.
    They should raise ValueError/TypeError/KeyError for an unsupported shape.
    """

    def parse_products_page(self, payload: Any) -> list[EktProduct]: ...

    def parse_product_detail(self, payload: Any) -> EktProduct: ...


class EktClient:
    """Async `httpx` client with server-only Basic Auth and safe GET operations.

    No retries are performed. This avoids duplicate operations by default and
    is safe for all currently implemented reads. Add retries only to documented
    idempotent requests after partner limits/semantics are confirmed.
    """

    def __init__(
        self,
        mapper: EktResponseMapper,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        settings = get_settings()
        username = settings.ekt_api_username
        password = settings.ekt_api_password
        if not username or password is None or not password.get_secret_value():
            raise EktConfigurationError(
                "Set EKT_API_USERNAME and EKT_API_PASSWORD in the server environment"
            )
        base_url = settings.ekt_api_base_url.strip()
        if not base_url.startswith(("https://", "http://")):
            raise EktConfigurationError("EKT_API_BASE_URL must be an absolute HTTP(S) URL")
        self._mapper = mapper
        self._timeout = timeout or httpx.Timeout(timeout=8.0, connect=3.0)
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            auth=httpx.BasicAuth(username, password.get_secret_value()),
            timeout=self._timeout,
            follow_redirects=False,
            transport=transport,
        )

    async def __aenter__(self) -> EktClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_products_page(self, page: int = 1) -> list[EktProduct]:
        """Fetch and normalize one catalog page (`GET /api/products?page=N`)."""
        if page < 1:
            raise ValueError("page must be greater than zero")
        payload = await self._get_json("list_products", PRODUCTS_PATH, params={"page": page})
        try:
            products = self._mapper.parse_products_page(payload)
            if not isinstance(products, list) or any(not isinstance(item, EktProduct) for item in products):
                raise TypeError("mapper must return list[EktProduct]")
            return products
        except EktClientError:
            raise
        except Exception as exc:
            self._log_failure("response_format", operation="list_products", error_type=type(exc).__name__)
            raise EktResponseFormatError("ekt.kz product-list response has an unsupported format") from None

    async def get_product_by_article(self, article: str, *, max_pages: int = 100) -> EktProduct:
        """Find an exact article in paginated catalog results.

        The partner API documentation supplied so far does not confirm a search
        query parameter. This method therefore uses only the documented `page`
        parameter and stops on an empty page, with a hard page bound.
        """
        normalized_article = article.strip().casefold()
        if not normalized_article:
            raise ValueError("article must not be empty")
        if not 1 <= max_pages <= 1000:
            raise ValueError("max_pages must be between 1 and 1000")
        for page in range(1, max_pages + 1):
            products = await self.get_products_page(page)
            if not products:
                raise EktProductNotFoundError("Product article was not found in the ekt.kz catalog")
            for product in products:
                if product.article.strip().casefold() == normalized_article:
                    return product
        self._log_failure("pagination_limit", operation="get_product_by_article")
        raise EktResponseFormatError("Catalog page limit reached before an empty page was returned")

    async def get_product_details(self, product_id: str) -> EktProduct:
        """Fetch a current product card (`GET /api/products/detail?id=...`)."""
        product_id = product_id.strip()
        if not product_id:
            raise ValueError("product_id must not be empty")
        payload = await self._get_json(
            "product_details", PRODUCT_DETAIL_PATH, params={"id": product_id}
        )
        try:
            product = self._mapper.parse_product_detail(payload)
            if not isinstance(product, EktProduct):
                raise TypeError("mapper must return EktProduct")
            return product
        except EktClientError:
            raise
        except Exception as exc:
            self._log_failure("response_format", operation="product_details", error_type=type(exc).__name__)
            raise EktResponseFormatError("ekt.kz product-detail response has an unsupported format") from None

    async def check_price(self, article: str) -> EktPriceCheck:
        """Refresh product details and return the verified price if supplied."""
        listed = await self.get_product_by_article(article)
        current = await self.get_product_details(listed.id)
        self._ensure_current_product_matches_listing(listed, current)
        if current.price is None:
            raise EktDataUnavailableError("Price is not available in the current product response")
        return EktPriceCheck(article=current.article, price=current.price)

    async def check_stock(self, article: str) -> EktStockCheck:
        """Refresh product details and return normalized per-location stock."""
        listed = await self.get_product_by_article(article)
        current = await self.get_product_details(listed.id)
        self._ensure_current_product_matches_listing(listed, current)
        if current.stock_by_location is None:
            raise EktDataUnavailableError("Stock is not available in the current product response")
        return EktStockCheck(article=current.article, stock_by_location=current.stock_by_location)

    def _ensure_current_product_matches_listing(self, listed: EktProduct, current: EktProduct) -> None:
        """Reject stale or malformed detail responses before reporting live data."""
        if current.id != listed.id or current.article.strip().casefold() != listed.article.strip().casefold():
            self._log_failure("product_mismatch", operation="product_details")
            raise EktResponseFormatError("ekt.kz product detail does not match the requested catalog item")

    async def _get_json(self, operation: str, path: str, *, params: dict[str, Any]) -> Any:
        try:
            response = await self._client.get(path, params=params)
        except httpx.TimeoutException as exc:
            self._log_failure("timeout", operation=operation, error_type=type(exc).__name__)
            raise EktTimeoutError("ekt.kz request timed out") from None
        except httpx.ConnectError as exc:
            self._log_failure("connection_error", operation=operation, error_type=type(exc).__name__)
            raise EktConnectionError("Could not connect to ekt.kz") from None
        except httpx.RequestError as exc:
            self._log_failure("connection_error", operation=operation, error_type=type(exc).__name__)
            raise EktConnectionError("ekt.kz request failed") from None

        if 400 <= response.status_code < 500:
            self._log_failure("http_client_error", operation=operation, status_code=response.status_code)
            if response.status_code in (401, 403):
                raise EktAuthenticationError("ekt.kz rejected server credentials")
            if response.status_code == 404:
                raise EktNotFoundError("Requested resource was not found on ekt.kz")
            raise EktClientRequestError(f"ekt.kz rejected the request (HTTP {response.status_code})")
        if response.status_code >= 500:
            self._log_failure("http_server_error", operation=operation, status_code=response.status_code)
            raise EktServerError(f"ekt.kz returned HTTP {response.status_code}")
        if not 200 <= response.status_code < 300:
            self._log_failure("unexpected_status", operation=operation, status_code=response.status_code)
            raise EktClientError(f"ekt.kz returned unexpected HTTP {response.status_code}")

        try:
            return response.json()
        except ValueError:
            self._log_failure("invalid_json", operation=operation, status_code=response.status_code)
            raise EktInvalidJsonError("ekt.kz returned invalid JSON") from None

    @staticmethod
    def _log_failure(event: str, *, operation: str, status_code: int | None = None, error_type: str | None = None) -> None:
        # Never log the request URL, headers, response body, or auth credentials.
        logger.warning(
            "ekt_api_failure",
            extra={
                "event": "ekt_api_failure",
                "failure_type": event,
                "operation": operation,
                "status_code": status_code,
                "error_type": error_type,
            },
        )
