"""Load a configured catalog adapter into the local PostgreSQL search index."""

from __future__ import annotations

import asyncio
import argparse
import logging

from app.config.database import SessionLocal, engine
from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.integrations.catalog_adapter import build_catalog_adapter, UnavailableCatalogAdapter
from app.repositories.catalog import CatalogRepository
from app.services.catalog import CatalogService


async def refresh_catalog(product_ids: list[str] | None = None) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    adapter = build_catalog_adapter()
    try:
        async with SessionLocal() as session:
            service = CatalogService(CatalogRepository(session), adapter=adapter)
            if isinstance(adapter, UnavailableCatalogAdapter):
                logging.getLogger("catalog_sync").warning("catalog_sync_skipped_missing_credentials")
                return
            from app.schemas.catalog import CatalogIndexRefresh
            count = 0
            for page in range(1, settings.catalog_sync_pages + 1):
                loaded = await service.load_source_page(page)
                count += len(loaded["candidates"])
                if not loaded["has_more"]:
                    break
            result = CatalogIndexRefresh(pages_loaded=page, products_loaded=count)
            for identifier in product_ids or []:
                await service.save_product(await adapter.get_product_details(identifier))
        logging.getLogger("catalog_sync").info(
            "catalog_index_refreshed", extra={"event": "catalog_index_refreshed", **result.model_dump()}
        )
    finally:
        await adapter.aclose()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-id", action="append", default=[], help="Also load a known EKT product ID")
    asyncio.run(refresh_catalog(parser.parse_args().product_id))
