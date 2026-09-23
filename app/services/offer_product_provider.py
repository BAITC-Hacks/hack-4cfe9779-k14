"""Fresh catalog-to-offer bridge; no cart operations live in this module."""

from app.integrations.ekt_client import EktConnectionError, EktDataUnavailableError, EktProduct
from app.services.catalog import CatalogService
from app.services.errors import ApplicationError


class CatalogCurrentProductProvider:
    """Adapts a fresh application-owned product card to OfferService's input."""

    def __init__(self, catalog: CatalogService) -> None:
        self._catalog = catalog

    async def get_current_product_by_article(self, article: str) -> EktProduct:
        try:
            product = await self._catalog.get_fresh_product(article, persist=False)
        except ApplicationError as exc:
            # OfferService deliberately uses no cache when a current source is unavailable.
            raise EktConnectionError("Current catalog product is unavailable") from exc
        if product.external_id is None:
            raise EktDataUnavailableError("Current catalog product has no source identifier")
        return EktProduct(
            id=product.external_id,
            article=product.article,
            name=product.name,
            price=product.cached_price,
            stock_by_location=product.cached_stock_by_location,
            attributes=product.characteristics,
            description=product.description,
            brand=product.brand,
            category=product.category,
            certificates=product.certificates,
            source_fields=product.source_fields,
            source_field_presence=product.source_field_presence,
        )
