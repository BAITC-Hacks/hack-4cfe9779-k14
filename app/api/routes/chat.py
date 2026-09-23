from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.integrations.llm_client import LLMConfigurationError, OpenAICompatibleLLMClient, UnavailableLLMClient
from app.repositories.catalog import CatalogRepository
from app.repositories.attachments import ChatAttachmentRepository
from app.repositories.chat import ChatRepository
from app.schemas.chat import ChatHistoryResponse, ChatMessageCreate, ChatReply, ChatSessionCreated
from app.services.catalog import CatalogService
from app.services.chat import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def get_chat_service(session: AsyncSession = Depends(get_db)) -> AsyncGenerator[ChatService, None]:
    try:
        llm = OpenAICompatibleLLMClient()
    except LLMConfigurationError:
        llm = UnavailableLLMClient()
    try:
        yield ChatService(
            repository=ChatRepository(session),
            catalog=CatalogService(CatalogRepository(session)),
            llm=llm,
            attachments=ChatAttachmentRepository(session),
        )
    finally:
        await llm.aclose()


Chat = Annotated[ChatService, Depends(get_chat_service)]


@router.post("/sessions", response_model=ChatSessionCreated, status_code=201)
async def create_chat_session(service: Chat) -> ChatSessionCreated:
    return await service.create_session()


@router.post("/sessions/{session_id}/messages", response_model=ChatReply)
async def send_chat_message(session_id: UUID, payload: ChatMessageCreate, service: Chat) -> ChatReply:
    return await service.send_message(session_id, payload)


@router.get("/sessions/{session_id}/messages", response_model=ChatHistoryResponse)
async def chat_history(session_id: UUID, service: Chat) -> ChatHistoryResponse:
    return await service.history(session_id)
