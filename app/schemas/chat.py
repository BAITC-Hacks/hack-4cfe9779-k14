from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.attachment_parsing import AttachmentItemMatch
from app.schemas.analogs import AnalogSuggestion
from app.schemas.purchase_conditions import PurchaseConditions


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatIntent(StrEnum):
    FIND_PRODUCT = "find_product"
    SEARCH_BY_REQUIREMENTS = "search_by_requirements"
    FIND_ANALOG = "find_analog"
    PRODUCT_CHARACTERISTICS = "product_characteristics"
    CHECK_PRICE = "check_price"
    CHECK_STOCK = "check_stock"
    CHECK_AVAILABILITY = "check_availability"
    CHECK_CERTIFICATES = "check_certificates"
    PURCHASE_CONDITIONS = "purchase_conditions"
    FOLLOW_UP = "follow_up"
    ADD_TO_CART_REQUEST = "add_to_cart_request"
    UNKNOWN = "unknown"


class SearchParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    characteristics: dict[str, Any] = Field(default_factory=dict)
    brand: str | None = Field(default=None, max_length=256)


class ChatSessionCreated(BaseModel):
    id: UUID
    created_at: datetime


class ChatMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=4000)
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def content_is_not_blank(self) -> "ChatMessageCreate":
        if not self.content.strip():
            raise ValueError("content must not be blank")
        if len(set(self.attachment_ids)) != len(self.attachment_ids):
            raise ValueError("attachment_ids must not contain duplicates")
        return self


class ChatMessageView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: ChatRole
    content: str
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    session_id: UUID
    messages: list[ChatMessageView]


class ChatAnalysis(BaseModel):
    """Validated LLM interpretation. It can request no server side action."""

    model_config = ConfigDict(extra="forbid")

    intent: ChatIntent
    article: str | None = Field(default=None, max_length=128)
    product_name: str | None = Field(default=None, max_length=512)
    quantity: int | None = Field(default=None, ge=1, le=10000)
    search_parameters: SearchParameters = Field(default_factory=SearchParameters)
    needs_clarification: bool = False
    clarification_question: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def clarification_has_question(self) -> "ChatAnalysis":
        if self.needs_clarification and not self.clarification_question:
            raise ValueError("clarification_question is required when clarification is needed")
        return self


class ChatReply(BaseModel):
    session_id: UUID
    user_message: ChatMessageView
    assistant_message: ChatMessageView
    analysis: ChatAnalysis
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    current_data: dict[str, Any] | None = None
    attachment_items: list[AttachmentItemMatch] = Field(default_factory=list)
    purchase_conditions: PurchaseConditions | None = None
    analogs: list[AnalogSuggestion] = Field(default_factory=list)
