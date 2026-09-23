"""Server-side cart boundary; EKT cart HTTP paths are intentionally absent.

The production implementation cannot be written before the partner provides a
cart contract. Runtime therefore exposes only an explicit unavailable gateway.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.schemas.offers import CartReference, CartSnapshot, CartWriteResult


class CartGatewayError(Exception):
    code = "cart_gateway_error"


class CartUnavailableError(CartGatewayError):
    code = "cart_unavailable"


class CartReadbackError(CartGatewayError):
    code = "cart_readback_invalid"


class CartGateway(Protocol):
    """Minimum operations required for a safe confirmed cart mutation."""

    @property
    def source_label(self) -> str: ...

    async def resolve_cart(self, *, session_id: UUID) -> CartReference: ...

    async def add_item(
        self,
        *,
        cart: CartReference,
        product_identifier: str,
        quantity: int,
        idempotency_key: str,
    ) -> CartWriteResult: ...

    async def set_item_quantity(
        self,
        *,
        cart: CartReference,
        product_identifier: str,
        quantity: int,
        idempotency_key: str,
    ) -> CartWriteResult: ...

    async def get_cart(self, *, cart: CartReference) -> CartSnapshot: ...


class UnavailableCartGateway:
    """Safe default until the partner documents cart identity, writes and reads."""

    source_label = "unavailable/no confirmed EKT cart contract"

    async def resolve_cart(self, *, session_id: UUID) -> CartReference:
        del session_id
        raise CartUnavailableError("Cart integration is not configured")

    async def add_item(
        self,
        *,
        cart: CartReference,
        product_identifier: str,
        quantity: int,
        idempotency_key: str,
    ) -> CartWriteResult:
        del cart, product_identifier, quantity, idempotency_key
        raise CartUnavailableError("Cart integration is not configured")

    async def set_item_quantity(
        self,
        *,
        cart: CartReference,
        product_identifier: str,
        quantity: int,
        idempotency_key: str,
    ) -> CartWriteResult:
        del cart, product_identifier, quantity, idempotency_key
        raise CartUnavailableError("Cart integration is not configured")

    async def get_cart(self, *, cart: CartReference) -> CartSnapshot:
        del cart
        raise CartUnavailableError("Cart integration is not configured")


def build_cart_gateway() -> CartGateway:
    """No cart write implementation exists until EKT documents a contract."""
    return UnavailableCartGateway()
