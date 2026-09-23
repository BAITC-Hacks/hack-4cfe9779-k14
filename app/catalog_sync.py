"""Load a configured catalog adapter into the local PostgreSQL search index."""

from __future__ import annotations

import asyncio
import logging

from app.config.database import SessionLocal, engine
from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.integrations.catalog_adapter import build_catalog_adapter
from app.repositories.catalog import CatalogRepository
from app.services.catalog import CatalogService


async def refresh_catalog() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    adapter = build_catalog_adapter()
    try:
        async with SessionLocal() as session:
            result = await CatalogService(CatalogRepository(session), adapter=adapter).refresh_index()
        logging.getLogger("catalog_sync").info(
            "catalog_index_refreshed", extra={"event": "catalog_index_refreshed", **result.model_dump()}
        )
    finally:
        await adapter.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(refresh_catalog())
