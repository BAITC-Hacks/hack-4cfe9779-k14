from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes.chat import get_chat_service
from app.main import app
from app.schemas.chat import ChatAnalysis, ChatHistoryResponse, ChatIntent, ChatMessageView, ChatReply, ChatRole, ChatSessionCreated


class ApiChatService:
    def __init__(self) -> None:
        self.session_id = uuid4()

    async def create_session(self):
        return ChatSessionCreated(id=self.session_id, created_at=datetime.now(timezone.utc))

    async def send_message(self, session_id, payload):
        now = datetime.now(timezone.utc)
        user = ChatMessageView(id=uuid4(), role=ChatRole.USER, content=payload.content, created_at=now)
        assistant = ChatMessageView(id=uuid4(), role=ChatRole.ASSISTANT, content="answer", created_at=now)
        return ChatReply(session_id=session_id, user_message=user, assistant_message=assistant, analysis=ChatAnalysis(intent=ChatIntent.UNKNOWN))

    async def history(self, session_id):
        return ChatHistoryResponse(session_id=session_id, messages=[])


def test_chat_endpoints_create_send_and_read_history() -> None:
    service = ApiChatService()
    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        with TestClient(app) as client:
            created = client.post("/api/chat/sessions")
            sent = client.post(f"/api/chat/sessions/{service.session_id}/messages", json={"content": "hello"})
            history = client.get(f"/api/chat/sessions/{service.session_id}/messages")
        assert created.status_code == 201
        assert sent.status_code == 200
        assert sent.json()["assistant_message"]["content"] == "answer"
        assert history.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_chat_message_rejects_blank_content() -> None:
    service = ApiChatService()
    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post(f"/api/chat/sessions/{service.session_id}/messages", json={"content": "  "})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
