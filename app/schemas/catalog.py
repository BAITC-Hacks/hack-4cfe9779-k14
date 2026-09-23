from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CatalogProductUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    article: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=512)
    external_id: str | None = Field(default=None, max_length=128)
    description: str | None = None
    brand: str | None = Field(default=None, max_length=256)
    characteristics: dict[str, Any] = Field(default_factory=dict)
    cached_price: Decimal | None = Field(default=None, ge=0)
    cached_stock_by_location: dict[str, int] | None = None
    cached_available: bool | None = None


class CatalogCandidate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    article: str
    external_id: str | None
    name: str
    description: str | None
    brand: str | None
    characteristics: dict[str, Any]
    # These values are a cache only; no endpoint marks them as current.
    cached_price: Decimal | None
    cached_stock_by_location: dict[str, int] | None
    cached_available: bool | None


class CatalogSearchResponse(BaseModel):
    candidates: list[CatalogCandidate]
    match_type: str


class CurrentAvailability(BaseModel):
    article: str
    price: Decimal | None
    stock_by_location: dict[str, int] | None
    available: bool | None
    current: bool
    reason: str | None = None
