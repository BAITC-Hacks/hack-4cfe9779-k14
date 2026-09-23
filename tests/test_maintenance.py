import pytest

from app.schemas.maintenance import CleanupResult
from app.services.maintenance import MaintenanceService

pytestmark = pytest.mark.asyncio


class FakeMaintenanceRepository:
    def __init__(self) -> None:
        self.called = False

    async def delete_expired(self, now, limit):
        assert now.tzinfo is not None
        assert limit > 0
        self.called = True
        return CleanupResult(expired_offers=2, expired_idempotency_keys=3, expired_attachments=4)


async def test_cleanup_service_removes_all_temporary_record_types() -> None:
    repository = FakeMaintenanceRepository()

    result = await MaintenanceService(repository).cleanup_expired()

    assert repository.called is True
    assert result.model_dump() == {"expired_offers": 2, "expired_idempotency_keys": 3, "expired_attachments": 4}
