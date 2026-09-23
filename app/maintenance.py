"""Operational commands that use the existing application database."""

from __future__ import annotations

import asyncio
import logging

from app.config.database import SessionLocal, engine
from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.repositories.maintenance import MaintenanceRepository
from app.services.maintenance import MaintenanceService


async def cleanup_expired() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger("maintenance")
    async with SessionLocal() as session:
        result = await MaintenanceService(MaintenanceRepository(session)).cleanup_expired()
    await engine.dispose()
    logger.info("temporary_data_cleaned", extra={"event": "temporary_data_cleaned", **result.model_dump()})


if __name__ == "__main__":
    asyncio.run(cleanup_expired())
