from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    IMAGE = "image"


class ExtractedTable(BaseModel):
    name: str
    rows: list[list[str | int | float | bool | None]] = Field(default_factory=list)


class AttachmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str
    mime_type: str
    document_type: DocumentType
    text: str = ""
    tables: list[ExtractedTable] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatAttachmentView(AttachmentResult):
    id: UUID
