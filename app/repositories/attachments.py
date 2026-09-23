from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import ChatAttachment
from app.schemas.attachments import AttachmentResult


class ChatAttachmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def store(self, session_id: UUID, result: AttachmentResult) -> ChatAttachment:
        attachment = ChatAttachment(
            session_id=session_id,
            filename=result.filename,
            mime_type=result.mime_type,
            document_type=result.document_type.value,
            extracted_text=result.text,
            tables=[table.model_dump(mode="json") for table in result.tables],
            warnings=result.warnings,
            metadata_json=result.metadata,
        )
        self.session.add(attachment)
        await self.session.commit()
        await self.session.refresh(attachment)
        return attachment

    async def get_for_session(self, session_id: UUID, attachment_ids: list[UUID]) -> Sequence[ChatAttachment]:
        if not attachment_ids:
            return []
        result = await self.session.execute(
            select(ChatAttachment).where(
                ChatAttachment.session_id == session_id,
                ChatAttachment.id.in_(attachment_ids),
            )
        )
        attachments = result.scalars().all()
        by_id = {attachment.id: attachment for attachment in attachments}
        return [by_id[attachment_id] for attachment_id in attachment_ids if attachment_id in by_id]
