from fastapi import APIRouter, File, UploadFile, status

from app.api.openapi import public_error_responses
from app.config.settings import get_settings
from app.schemas.attachments import AttachmentResult
from app.services.attachments import AttachmentService
from app.services.errors import AttachmentTooLarge

router = APIRouter(prefix="/api/attachments", tags=["attachments"])


@router.post(
    "",
    response_model=AttachmentResult,
    status_code=status.HTTP_201_CREATED,
    operation_id="extract_attachment",
    summary="Validate and extract a standalone attachment",
    responses=public_error_responses(413, 415, 422),
)
async def upload_attachment(file: UploadFile = File(...)) -> AttachmentResult:
    """Extract supported user documents; content is not sent to an LLM."""
    content = await _read_limited(file, get_settings().attachment_max_bytes)
    return AttachmentService().process(file.filename or "upload", file.content_type, content)


async def _read_limited(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    try:
        while chunk := await file.read(64 * 1024):
            size += len(chunk)
            if size > max_bytes:
                raise AttachmentTooLarge(f"Attachment exceeds {max_bytes} bytes")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        await file.close()
