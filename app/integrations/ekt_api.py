"""HTTP adapter for the partner ekt.kz product API.

The exact response schema is not yet documented. This adapter supports common
list envelopes and keeps schema-specific parsing in one place for adjustment
when the partner confirms the real contract.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class EktApiError(RuntimeError):
    """Base error for upstream API failures; does not expose credentials."""


class EktApiUnavailable(EktApiError):
    """The upstream service could not be reached or returned an error."""


class EktApiContractError(EktApiError):
    """The upstream response did not match a supported response shape."""


class EktProduct(BaseModel):
    """Normalized product fields; optional values stay unknown when absent."""

    model_config = ConfigDict(extra="allow")

    id: str
    article: str | None = None
    name: str
    category: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    certificate_links: list[str] = Field(default_factory=list)
    price: float | None = None
    warehouse_stocks: dict[str, int] = Field(default_factory=dict)
    product_url: str | None = None
    updated_at: str | None = None


class EktApiClient:
    """Async API client; credentials are read from server environment only."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout_seconds: float = 8.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("EKT_API_BASE_URL", "https://ekt.kz/api/")).rstrip("/") + "/"
        self.username = username if username is not None else os.getenv("EKT_API_USERNAME")
        self.password = password if password is not None else os.getenv("EKT_API_PASSWORD")
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        if not self.username or not self.password:
            raise ValueError("EKT_API_USERNAME and EKT_API_PASSWORD must be configured")

    async def __aenter__(self) -> EktApiClient:
        self._client = httpx.AsyncClient(
            auth=httpx.BasicAuth(self.username, self.password),
            timeout=httpx.Timeout(self.timeout_seconds),
            transport=self.transport,
            follow_redirects=False,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await self._client.aclose()

    async def aclose(self) -> None:
        client = getattr(self, "_client", None)
        if client is not None:
            await client.aclose()

    async def list_products(self, *, page: int = 1) -> list[EktProduct]:
        if page < 1:
            raise ValueError("page must be a positive integer")
        payload = await self._get_json("products", params={"page": page})
        rows = self._extract_rows(payload)
        return [self._normalize_product(row) for row in rows]

    async def get_product(self, product_id: str) -> EktProduct:
        payload = await self._get_json("products/detail", params={"id": product_id})
        if not isinstance(payload, dict):
            raise EktApiContractError("Product detail response must be a JSON object")
        row = payload.get("product", payload.get("data", payload))
        if not isinstance(row, dict):
            raise EktApiContractError("Product detail response has no product object")
        return self._normalize_product(row)

    async def _get_json(self, path: str, *, params: dict[str, Any]) -> Any:
        client = getattr(self, "_client", None)
        if client is None:
            raise RuntimeError("Use EktApiClient as an async context manager")
        url = urljoin(self.base_url, path.lstrip("/"))
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise EktApiUnavailable(f"ekt.kz API returned HTTP {exc.response.status_code}") from None
        except (httpx.HTTPError, ValueError) as exc:
            raise EktApiUnavailable(f"ekt.kz API request failed: {type(exc).__name__}") from None

    @staticmethod
    def _extract_rows(payload: Any) -> list[dict[str, Any]]:
        rows: Any = payload
        if isinstance(payload, dict):
            for key in ("products", "items", "results", "data"):
                if key in payload:
                    rows = payload[key]
                    break
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise EktApiContractError("Product list response is not a supported list envelope")
        return rows

    @staticmethod
    def _normalize_product(row: dict[str, Any]) -> EktProduct:
        # Aliases are intentionally centralized and conservative. Confirm these
        # keys against the real partner schema before relying on populated values.
        candidate = {
            "id": row.get("id", row.get("product_id", row.get("sku"))),
            "article": row.get("article", row.get("sku")),
            "name": row.get("name", row.get("title")),
            "category": row.get("category"),
            "attributes": row.get("attributes", {}),
            "certificate_links": row.get("certificate_links", row.get("certificates", [])),
            "price": row.get("price"),
            "warehouse_stocks": row.get("warehouse_stocks", row.get("stocks", {})),
            "product_url": row.get("product_url", row.get("url")),
            "updated_at": row.get("updated_at"),
        }
        if candidate["id"] is None or candidate["name"] is None:
            raise EktApiContractError("Product is missing required id/name fields")
        if not isinstance(candidate["attributes"], dict):
            candidate["attributes"] = {}
        if not isinstance(candidate["certificate_links"], list):
            candidate["certificate_links"] = []
        if not isinstance(candidate["warehouse_stocks"], dict):
            candidate["warehouse_stocks"] = {}
        try:
            return EktProduct.model_validate(candidate)
        except ValidationError as exc:
            raise EktApiContractError(f"Product fields failed validation ({exc.error_count()} errors)") from None
