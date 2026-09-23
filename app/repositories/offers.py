from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatSession
from app.models.temporary import IdempotencyKey, PendingOffer


class OfferRepository:
    """Persistence primitives used only inside the offer-service transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        async with self.session.begin():
            yield

    async def session_exists(self, session_id: UUID) -> bool:
        result = await self.session.execute(select(ChatSession.id).where(ChatSession.id == session_id))
        return result.scalar_one_or_none() is not None

    async def create_offer(self, offer: PendingOffer) -> PendingOffer:
        self.session.add(offer)
        await self.session.flush()
        return offer

    async def lock_offer(self, offer_id: UUID, session_id: UUID) -> PendingOffer | None:
        result = await self.session.execute(
            select(PendingOffer)
            .where(PendingOffer.id == offer_id, PendingOffer.session_id == session_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def lock_idempotency_key(self, scope: str, key: str) -> IdempotencyKey | None:
        result = await self.session.execute(
            select(IdempotencyKey)
            .where(IdempotencyKey.scope == scope, IdempotencyKey.key == key)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def reserve_idempotency_key(self, scope: str, key: str, expires_at: datetime) -> IdempotencyKey:
        record = IdempotencyKey(scope=scope, key=key, expires_at=expires_at)
        self.session.add(record)
        await self.session.flush()
        return record

    async def save(self) -> None:
        await self.session.flush()
