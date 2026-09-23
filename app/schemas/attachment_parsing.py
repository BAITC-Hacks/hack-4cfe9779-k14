from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.attachments import DocumentType


class AttachmentLlmContext(BaseModel):
    attachment_id: UUID
    filename: str
    document_type: DocumentType
    text: str
    warnings: list[str] = Field(default_factory=list)


class ParsedAttachmentItem(BaseModel):
    attachment_id: UUID
    article: str | None = None
    product_name: str | None = None
    quantity: int | None = Field(default=None, ge=1)
    warnings: list[str] = Field(default_factory=list)


class AttachmentItemMatch(ParsedAttachmentItem):
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    current_data: dict[str, Any] | None = None
