"""Server-side cart boundary; EKT cart HTTP paths are intentionally absent.

The production implementation cannot be written before the partner provides a
cart contract. The mock adapter is deterministic demo infrastructure only.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Protocol
from uuid import UUID

from app.config.settings import get_settings
from app.schemas.offers import CartItem, CartReference, CartSnapshot, CartWriteResult


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


class MockCartGateway:
    """In-memory mock/demo cart; not an EKT implementation or persistent store."""

    source_label = "mock/demo cart adapter (not ekt.kz)"

    def __init__(self) -> None:
        self._items: dict[str, dict[str, int]] = {}
        self._owners: dict[str, UUID] = {}
        self._operations: dict[tuple[str, str], CartWriteResult] = {}
        self._lock = asyncio.Lock()

    async def resolve_cart(self, *, session_id: UUID) -> CartReference:
        cart_id = f"mock-session-{session_id}"
        async with self._lock:
            owner = self._owners.setdefault(cart_id, session_id)
            if owner != session_id:
                raise CartGatewayError("Cart owner does not match the chat session")
            self._items.setdefault(cart_id, {})
        return CartReference(cart_id=cart_id, owner_session_id=session_id)

    async def add_item(
        self,
        *,
        cart: CartReference,
        product_identifier: str,
        quantity: int,
        idempotency_key: str,
    ) -> CartWriteResult:
        return await self._write(
            cart=cart,
            product_identifier=product_identifier,
            quantity=quantity,
            idempotency_key=idempotency_key,
            replace=False,
        )

    async def set_item_quantity(
        self,
        *,
        cart: CartReference,
        product_identifier: str,
        quantity: int,
        idempotency_key: str,
    ) -> CartWriteResult:
        return await self._write(
            cart=cart,
            product_identifier=product_identifier,
            quantity=quantity,
            idempotency_key=idempotency_key,
            replace=True,
        )

    async def get_cart(self, *, cart: CartReference) -> CartSnapshot:
        async with self._lock:
            self._assert_owner(cart)
            items = self._items.get(cart.cart_id, {})
            return CartSnapshot(
                cart_id=cart.cart_id,
                items=[CartItem(product_identifier=product_id, quantity=quantity) for product_id, quantity in sorted(items.items())],
                cart_url=f"mock://cart/{cart.cart_id}",
                source_label=self.source_label,
            )

    async def _write(
        self,
        *,
        cart: CartReference,
        product_identifier: str,
        quantity: int,
        idempotency_key: str,
        replace: bool,
    ) -> CartWriteResult:
        if quantity < 1:
            raise CartGatewayError("Cart quantity must be positive")
        async with self._lock:
            self._assert_owner(cart)
            operation_key = (cart.cart_id, idempotency_key)
            existing = self._operations.get(operation_key)
            if existing is not None:
                return existing
            items = self._items.setdefault(cart.cart_id, {})
            items[product_identifier] = quantity if replace else items.get(product_identifier, 0) + quantity
            result = CartWriteResult(cart_id=cart.cart_id, operation_id=f"mock-op-{idempotency_key}")
            self._operations[operation_key] = result
            return result

    def _assert_owner(self, cart: CartReference) -> None:
        if self._owners.get(cart.cart_id) != cart.owner_session_id:
            raise CartGatewayError("Cart owner does not match the chat session")


@lru_cache
def build_cart_gateway() -> CartGateway:
    """Return a process-local demo cart only when explicitly configured."""
    if get_settings().cart_adapter_mode == "mock":
        return MockCartGateway()
    return UnavailableCartGateway()
