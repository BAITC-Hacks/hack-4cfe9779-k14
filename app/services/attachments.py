from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from PIL import Image, UnidentifiedImageError

from app.config.settings import get_settings
from app.extractors.attachments import (
    AttachmentExtractionError,
    DocxExtractor,
    ImageOcrExtractor,
    PdfExtractor,
    XlsxExtractor,
)
from app.schemas.attachments import AttachmentResult, DocumentType
from app.services.errors import AttachmentProcessingFailed, AttachmentTooLarge, UnsupportedAttachment


class AttachmentService:
    """Validates bytes and delegates extraction without passing files to the LLM."""

    _EXPECTED_MIME = {
        DocumentType.PDF: "application/pdf",
        DocumentType.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        DocumentType.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        DocumentType.IMAGE: {"image/jpeg", "image/png"},
    }
    _EXTENSIONS = {
        ".pdf": DocumentType.PDF,
        ".docx": DocumentType.DOCX,
        ".xlsx": DocumentType.XLSX,
        ".jpg": DocumentType.IMAGE,
        ".jpeg": DocumentType.IMAGE,
        ".png": DocumentType.IMAGE,
    }

    def __init__(self) -> None:
        settings = get_settings()
        self.max_bytes = settings.attachment_max_bytes
        self._extractors = {
            DocumentType.PDF: PdfExtractor(),
            DocumentType.DOCX: DocxExtractor(),
            DocumentType.XLSX: XlsxExtractor(
                max_sheets=settings.attachment_max_xlsx_sheets,
                max_rows=settings.attachment_max_xlsx_rows,
                max_columns=settings.attachment_max_xlsx_columns,
                max_uncompressed_bytes=settings.attachment_max_bytes * 5,
            ),
            DocumentType.IMAGE: ImageOcrExtractor(),
        }

    def process(self, filename: str, claimed_mime_type: str | None, content: bytes) -> AttachmentResult:
        safe_filename = Path(filename or "upload").name
        if not content:
            raise AttachmentProcessingFailed("Attachment is empty")
        if len(content) > self.max_bytes:
            raise AttachmentTooLarge(f"Attachment exceeds {self.max_bytes} bytes")
        extension_type = self._EXTENSIONS.get(Path(safe_filename).suffix.lower())
        if extension_type is None:
            raise UnsupportedAttachment("Supported formats are PDF, DOCX, XLSX, JPEG, and PNG")
        detected_type, detected_mime = self._detect_type(content)
        if detected_type != extension_type:
            raise UnsupportedAttachment("Filename extension does not match file contents")
        expected_mime = self._EXPECTED_MIME[detected_type]
        if isinstance(expected_mime, set):
            if claimed_mime_type not in expected_mime or claimed_mime_type != detected_mime:
                raise UnsupportedAttachment("Declared MIME type does not match image contents")
        elif claimed_mime_type != expected_mime:
            raise UnsupportedAttachment("Declared MIME type does not match file contents")
        try:
            return self._extractors[detected_type].extract(safe_filename, detected_mime, content)
        except AttachmentExtractionError as exc:
            raise AttachmentProcessingFailed(str(exc)) from exc

    @staticmethod
    def _detect_type(content: bytes) -> tuple[DocumentType, str]:
        if content.startswith(b"%PDF-"):
            return DocumentType.PDF, "application/pdf"
        if content.startswith(b"PK\x03\x04"):
            try:
                with ZipFile(BytesIO(content)) as archive:
                    names = set(archive.namelist())
            except BadZipFile as exc:
                raise UnsupportedAttachment("Invalid ZIP-based office file") from exc
            if "[Content_Types].xml" in names and any(name.startswith("word/") for name in names):
                return DocumentType.DOCX, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if "[Content_Types].xml" in names and any(name.startswith("xl/") for name in names):
                return DocumentType.XLSX, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            raise UnsupportedAttachment("Unsupported ZIP-based document")
        try:
            with Image.open(BytesIO(content)) as image:
                image.verify()
                if image.format == "JPEG":
                    return DocumentType.IMAGE, "image/jpeg"
                if image.format == "PNG":
                    return DocumentType.IMAGE, "image/png"
        except (UnidentifiedImageError, OSError, ValueError):
            pass
        raise UnsupportedAttachment("File content is not a supported document type")
