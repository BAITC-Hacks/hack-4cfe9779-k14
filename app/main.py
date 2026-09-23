from __future__ import annotations

import hashlib
import os
import re
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Protocol

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="EKT Chat API", version="0.2.0")

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENTS_PER_MESSAGE = 5
PROPOSAL_TTL = timedelta(minutes=5)
ALLOWED_TYPES = {
    "application/pdf": {".pdf"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
    "application/msword": {".doc"},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {".xlsx"},
    "application/vnd.ms-excel": {".xls"},
    "image/jpeg": {".jpg", ".jpeg"},
}
UPLOAD_DIR = Path(tempfile.gettempdir()) / "ekt-chat-uploads"
UPLOAD_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_ATTACHMENTS_PER_MESSAGE)


class ProductLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1, max_length=128)
    quantity: int = Field(gt=0, le=10000)


class PendingProposal(BaseModel):
    id: uuid.UUID
    lines: list[ProductLine] = Field(min_length=1, max_length=100)
    expires_at: datetime


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: uuid.UUID


class ProductCard(BaseModel):
    product_id: str
    article: str | None = None
    name: str
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    available_quantity: int | None = Field(default=None, ge=0)
    certificate_url: str | None = None
    product_url: str | None = None


class ChatResponse(BaseModel):
    message: str
    products: list[ProductCard] = Field(default_factory=list)
    proposal: PendingProposal | None = None


class UploadResponse(BaseModel):
    attachment_id: uuid.UUID
    filename: str
    content_type: str
    size: int


class CartResult(BaseModel):
    """Result from the website adapter after it has confirmed the cart write."""

    added_lines: list[ProductLine]
    cart_url: str


class AttachmentRecord(BaseModel):
    session: str
    filename: str
    content_type: str
    size: int
    sha256: str
    path: Path


class ChatProcessor(Protocol):
    async def respond(self, message: str, attachment_paths: list[Path]) -> ChatResponse: ...


class CartAdapter(Protocol):
    async def add_confirmed(self, lines: list[ProductLine], session: str, idempotency_key: str) -> CartResult: ...


class NotConfiguredProcessor:
    async def respond(self, message: str, attachment_paths: list[Path]) -> ChatResponse:
        del message, attachment_paths
        return ChatResponse(message="Поиск каталога и обработчик вложений ещё не подключены.")


class NotConfiguredCart:
    async def add_confirmed(self, lines: list[ProductLine], session: str, idempotency_key: str) -> CartResult:
        del lines, session, idempotency_key
        raise HTTPException(status_code=503, detail="Корзина сайта ещё не подключена; товар не добавлен")


# Replace with implementations supplied by the integrating team. The interfaces
# keep model, file parsing and website/cart code outside the HTTP routes.
chat_processor: ChatProcessor = NotConfiguredProcessor()
cart_adapter: CartAdapter = NotConfiguredCart()

# In-memory state is intentionally used for this database-free MVP. It is local
# to one process and should later be replaced by the team's chosen shared store.
proposals: dict[tuple[str, uuid.UUID], PendingProposal] = {}
attachments: dict[uuid.UUID, AttachmentRecord] = {}
idempotency_results: dict[tuple[str, str], dict] = {}


async def get_session(
    x_chat_session: Annotated[str | None, Header(alias="X-Chat-Session")] = None,
) -> str:
    """Development session header; production should inject authenticated site session."""
    session = (x_chat_session or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", session):
        raise HTTPException(status_code=401, detail="Нужна действующая сессия сайта")
    return session


Session = Annotated[str, Depends(get_session)]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat/messages", response_model=ChatResponse)
async def send_message(payload: ChatRequest, session: Session) -> ChatResponse:
    if not payload.message.strip() and not payload.attachment_ids:
        raise HTTPException(status_code=422, detail="Добавьте сообщение или вложение")
    paths: list[Path] = []
    for attachment_id in payload.attachment_ids:
        record = attachments.get(attachment_id)
        if record is None or record.session != session:
            raise HTTPException(status_code=404, detail="Вложение не найдено в этой сессии")
        paths.append(record.path)

    response = await chat_processor.respond(payload.message.strip(), paths)
    if response.proposal:
        response.proposal.expires_at = datetime.now(timezone.utc) + PROPOSAL_TTL
        proposals[(session, response.proposal.id)] = response.proposal
    return response


@app.post(
    "/api/chat/attachments",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(session: Session, file: UploadFile = File(...)) -> UploadResponse:
    filename = Path(file.filename or "file").name
    suffix = Path(filename).suffix.lower()
    content_type = (file.content_type or "").lower()
    if suffix not in ALLOWED_TYPES.get(content_type, set()):
        raise HTTPException(status_code=415, detail="Поддерживаются PDF, Word, Excel и JPEG")

    attachment_id = uuid.uuid4()
    destination = UPLOAD_DIR / str(attachment_id)
    size = 0
    digest = hashlib.sha256()
    try:
        with destination.open("xb") as out:
            os.chmod(destination, 0o600)
            while chunk := await file.read(64 * 1024):
                size += len(chunk)
                if size > MAX_FILE_BYTES:
                    raise HTTPException(status_code=413, detail="Файл больше 10 МБ")
                digest.update(chunk)
                out.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    attachments[attachment_id] = AttachmentRecord(
        session=session,
        filename=filename,
        content_type=content_type,
        size=size,
        sha256=digest.hexdigest(),
        path=destination,
    )
    return UploadResponse(
        attachment_id=attachment_id,
        filename=filename,
        content_type=content_type,
        size=size,
    )


@app.post("/api/chat/confirm", response_model=CartResult)
async def confirm_cart(
    payload: ConfirmRequest,
    session: Session,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
) -> CartResult:
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", idempotency_key):
        raise HTTPException(status_code=400, detail="Некорректный ключ повтора")
    cached = idempotency_results.get((session, idempotency_key))
    if cached is not None:
        return CartResult.model_validate(cached)

    key = (session, payload.proposal_id)
    proposal = proposals.get(key)
    if proposal is None or proposal.expires_at <= datetime.now(timezone.utc):
        proposals.pop(key, None)
        raise HTTPException(status_code=409, detail="Предложение не найдено или устарело")

    # Keep the proposal if the external cart adapter is unavailable; only consume
    # it after a successful write, so the user can retry with a new idempotency key.
    result = await cart_adapter.add_confirmed(proposal.lines, session, idempotency_key)
    proposals.pop(key, None)
    body = result.model_dump(mode="json")
    idempotency_results[(session, idempotency_key)] = body
    return result
