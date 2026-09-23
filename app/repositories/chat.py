import secrets
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatSession, Message
from app.schemas.chat import ChatRole


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_session(self) -> ChatSession:
        chat_session = ChatSession(external_key=secrets.token_urlsafe(32))
        self.session.add(chat_session)
        await self.session.commit()
        await self.session.refresh(chat_session)
        return chat_session

    async def get_session(self, session_id: UUID) -> ChatSession | None:
        result = await self.session.execute(select(ChatSession).where(ChatSession.id == session_id))
        return result.scalar_one_or_none()

    async def add_message(self, session_id: UUID, role: ChatRole, content: str, metadata: dict | None = None) -> Message:
        message = Message(session_id=session_id, role=role.value, content=content, metadata_json=metadata or {})
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def history(self, session_id: UUID, *, limit: int | None = None) -> Sequence[Message]:
        statement = select(Message).where(Message.session_id == session_id).order_by(Message.created_at, Message.id)
        if limit is not None:
            statement = (
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(desc(Message.created_at), desc(Message.id))
                .limit(limit)
            )
            result = await self.session.execute(statement)
            return list(reversed(result.scalars().all()))
        result = await self.session.execute(statement)
        return result.scalars().all()
