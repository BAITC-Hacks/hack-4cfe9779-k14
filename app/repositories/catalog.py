from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.schemas.catalog import CatalogProductUpsert


class CatalogRepository:
    """PostgreSQL persistence and queries for the local product catalog."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, payload: CatalogProductUpsert) -> Product:
        values = payload.model_dump()
        statement = insert(Product).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[Product.article],
            set_={key: getattr(statement.excluded, key) for key in values if key != "article"},
        ).returning(Product)
        result = await self.session.execute(statement)
        await self.session.commit()
        return result.scalar_one()

    async def find_by_article(self, article: str) -> Product | None:
        result = await self.session.execute(select(Product).where(Product.article == article))
        return result.scalar_one_or_none()

    async def full_text_search(
        self,
        query: str | None,
        *,
        characteristics: dict[str, Any] | None = None,
        limit: int = 20,
    ) -> Sequence[Product]:
        if query:
            search_query = func.plainto_tsquery("simple", query)
            statement: Select[tuple[Product]] = (
                select(Product)
                .where(Product.search_vector.op("@@")(search_query))
                .order_by(func.ts_rank_cd(Product.search_vector, search_query).desc(), Product.name)
                .limit(limit)
            )
        else:
            statement = select(Product).order_by(Product.name).limit(limit)
        if characteristics:
            statement = statement.where(Product.characteristics.contains(characteristics))
        result = await self.session.execute(statement)
        return result.scalars().all()
