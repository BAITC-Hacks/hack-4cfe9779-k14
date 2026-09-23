from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.attachments import _read_limited
from app.config.database import get_db
from app.config.settings import get_settings
from app.repositories.attachments import ChatAttachmentRepository
from app.repositories.chat import ChatRepository
from app.schemas.attachments import ChatAttachmentView
from app.services.attachments import AttachmentService
from app.services.errors import ResourceNotFound

router = APIRouter(prefix="/api/chat/sessions", tags=["chat"])


async def get_attachment_repository(session: AsyncSession = Depends(get_db)) -> AsyncGenerator[ChatAttachmentRepository, None]:
    yield ChatAttachmentRepository(session)


Attachments = Annotated[ChatAttachmentRepository, Depends(get_attachment_repository)]


@router.post("/{session_id}/attachments", response_model=ChatAttachmentView, status_code=status.HTTP_201_CREATED)
async def upload_chat_attachment(
    session_id: UUID,
    attachments: Attachments,
    session: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
) -> ChatAttachmentView:
    """Extract an attachment, then persist only its normalized result for this chat session."""
    if await ChatRepository(session).get_session(session_id) is None:
        await file.close()
        raise ResourceNotFound("Chat session was not found")
    result = AttachmentService().process(
        file.filename or "upload",
        file.content_type,
        await _read_limited(file, get_settings().attachment_max_bytes),
    )
    attachment = await attachments.store(
        session_id,
        result,
        datetime.now(timezone.utc) + timedelta(seconds=get_settings().attachment_ttl_seconds),
    )
    return ChatAttachmentView(id=attachment.id, **result.model_dump())
