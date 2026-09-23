from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.config.settings import get_settings
from app.integrations.responses_consultant import ResponsesConsultant
from app.integrations.llm_client import LLMConfigurationError, OpenAICompatibleLLMClient, UnavailableLLMClient
from app.integrations.catalog_adapter import build_catalog_adapter
from app.api.routes.offers import get_offer_service
from app.repositories.catalog import CatalogRepository
from app.repositories.attachments import ChatAttachmentRepository
from app.repositories.chat import ChatRepository
from app.schemas.chat import ChatHistoryResponse, ChatMessageCreate, ChatReply, ChatSessionCreated
from app.services.catalog import CatalogService
from app.services.analogs import AnalogService
from app.services.chat import ChatService
from app.services.offers import OfferService

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def get_chat_service(session: AsyncSession = Depends(get_db), offers: OfferService = Depends(get_offer_service)) -> AsyncGenerator[ChatService, None]:
    try:
        llm = ResponsesConsultant() if get_settings().openai_api_key else OpenAICompatibleLLMClient()
    except LLMConfigurationError:
        llm = UnavailableLLMClient()
    adapter = build_catalog_adapter()
    try:
        catalog = CatalogService(CatalogRepository(session, source_origin="ekt/live" if get_settings().catalog_adapter_mode == "ekt" else "mock/demo"), adapter=adapter)
        yield ChatService(
            repository=ChatRepository(session),
            catalog=catalog,
            llm=llm,
            attachments=ChatAttachmentRepository(session),
            analogs=AnalogService(catalog),
            offer_proposals=offers,
        )
    finally:
        await llm.aclose()
        await adapter.aclose()


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
