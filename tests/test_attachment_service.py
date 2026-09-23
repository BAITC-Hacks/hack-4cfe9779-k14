from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services.attachments import AttachmentService
from app.services.errors import AttachmentProcessingFailed, AttachmentTooLarge, UnsupportedAttachment


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (5, 5), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_attachment_service_rejects_extension_content_and_mime_mismatches() -> None:
    service = AttachmentService()
    content = png_bytes()

    with pytest.raises(UnsupportedAttachment):
        service.process("image.jpg", "image/jpeg", content)
    with pytest.raises(UnsupportedAttachment):
        service.process("image.png", "image/jpeg", content)
    with pytest.raises(UnsupportedAttachment):
        service.process("legacy.xls", "application/vnd.ms-excel", content)


def test_attachment_service_rejects_empty_and_oversized_files(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AttachmentService()
    with pytest.raises(AttachmentProcessingFailed):
        service.process("empty.pdf", "application/pdf", b"")
    service.max_bytes = 1
    with pytest.raises(AttachmentTooLarge):
        service.process("image.png", "image/png", png_bytes())


def test_attachment_service_reports_damaged_pdf_as_processing_error() -> None:
    with pytest.raises(AttachmentProcessingFailed):
        AttachmentService().process("damaged.pdf", "application/pdf", b"%PDF-broken")


def test_upload_endpoint_validates_multipart_and_returns_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.extractors.attachments.pytesseract.image_to_string", lambda image: "image text")
    with TestClient(app) as client:
        response = client.post("/api/attachments", files={"file": ("image.png", png_bytes(), "image/png")})

    assert response.status_code == 201
    assert response.json()["document_type"] == "image"
    assert response.json()["text"] == "image text"
