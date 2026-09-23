from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import ChatAttachment
from app.models.temporary import IdempotencyKey, PendingOffer
from app.schemas.maintenance import CleanupResult


class MaintenanceRepository:
    """Deletes expired temporary data in bounded batches."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def delete_expired(self, now: datetime, limit: int) -> CleanupResult:
        offers = await self._delete_limited(PendingOffer, PendingOffer.expires_at, now, limit)
        keys = await self._delete_limited(IdempotencyKey, IdempotencyKey.expires_at, now, limit)
        attachments = await self._delete_limited(ChatAttachment, ChatAttachment.expires_at, now, limit)
        await self.session.commit()
        return CleanupResult(
            expired_offers=offers,
            expired_idempotency_keys=keys,
            expired_attachments=attachments,
        )

    async def _delete_limited(self, model, expires_at, now: datetime, limit: int) -> int:
        identifiers = (
            select(model.id)
            .where(expires_at <= now)
            .order_by(expires_at)
            .limit(limit)
            .subquery()
        )
        result = await self.session.execute(delete(model).where(model.id.in_(select(identifiers.c.id))))
        return result.rowcount or 0
