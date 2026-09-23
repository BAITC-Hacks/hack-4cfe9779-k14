"""Cart mutation interface. A real EKT implementation requires partner docs."""

from typing import Protocol
from uuid import UUID

from app.schemas.offers import CartWriteResult


class CartGatewayError(Exception):
    code = "cart_gateway_error"


class CartUnavailableError(CartGatewayError):
    code = "cart_unavailable"


class CartGateway(Protocol):
    async def add_item(
        self,
        *,
        session_id: UUID,
        product_identifier: str,
        quantity: int,
        idempotency_key: str,
    ) -> CartWriteResult: ...


class UnavailableCartGateway:
    """Never simulates a write when the partner cart contract is unavailable."""

    async def add_item(
        self,
        *,
        session_id: UUID,
        product_identifier: str,
        quantity: int,
        idempotency_key: str,
    ) -> CartWriteResult:
        del session_id, product_identifier, quantity, idempotency_key
        raise CartUnavailableError("Cart integration is not configured")
