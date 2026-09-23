from datetime import datetime
from decimal import Decimal
from enum import StrEnum
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


class ConfirmOfferResult(BaseModel):
    offer: PendingOfferView
    outcome: str
    cart_url: str | None = None
    message: str


class CartWriteResult(BaseModel):
    cart_url: str
