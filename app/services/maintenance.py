from datetime import datetime, timezone

from app.config.settings import get_settings
from app.repositories.maintenance import MaintenanceRepository
from app.schemas.maintenance import CleanupResult


class MaintenanceService:
    def __init__(self, repository: MaintenanceRepository) -> None:
        self._repository = repository
        self._batch_size = get_settings().cleanup_batch_size

    async def cleanup_expired(self) -> CleanupResult:
        return await self._repository.delete_expired(datetime.now(timezone.utc), self._batch_size)
