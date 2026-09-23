from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class PendingOfferStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    REJECTED = "rejected"
    FAILED = "failed"


class CreateOfferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_identifier: str = Field(min_length=1, max_length=128)
    article: str = Field(min_length=1, max_length=128)
    quantity: int = Field(ge=1, le=10000)


class PendingOfferView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    offer_id: UUID = Field(validation_alias=AliasChoices("id", "offer_id"))
    session_id: UUID
    product_identifier: str
    article: str
    quantity: int
    price_at_offer: Decimal
    created_at: datetime
    expires_at: datetime
    status: PendingOfferStatus
    # Server-owned binding. A client never supplies a cart identifier here.
    cart_context: dict[str, Any] = Field(default_factory=dict)


class ConfirmOfferResult(BaseModel):
    offer: PendingOfferView
    outcome: str
    cart_url: str | None = None
    cart: "CartSnapshot | None" = None
    message: str


class CartReference(BaseModel):
    """Opaque cart identity resolved server-side for one chat session."""

    cart_id: str = Field(min_length=1, max_length=256)
    owner_session_id: UUID


class CartItem(BaseModel):
    product_identifier: str = Field(min_length=1, max_length=128)
    quantity: int = Field(ge=1, le=10000)


class CartWriteResult(BaseModel):
    """Adapter write receipt, never a substitute for final cart state."""

    cart_id: str = Field(min_length=1, max_length=256)
    operation_id: str = Field(min_length=1, max_length=256)


class CartSnapshot(BaseModel):
    """Cart state read back after a confirmed write."""

    cart_id: str = Field(min_length=1, max_length=256)
    items: list[CartItem] = Field(default_factory=list)
    # None means the adapter has no confirmed cart link to return.
    cart_url: str | None = Field(default=None, max_length=2048)
    source_label: str = Field(min_length=1, max_length=256)
