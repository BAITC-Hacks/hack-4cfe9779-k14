"""PostgreSQL product catalog with JSONB attributes and text search."""

from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.integrations.ekt_api import EktProduct


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    article TEXT,
    name TEXT NOT NULL,
    category TEXT,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    certificate_links JSONB NOT NULL DEFAULT '[]'::jsonb,
    price NUMERIC(14, 2),
    warehouse_stocks JSONB NOT NULL DEFAULT '{}'::jsonb,
    product_url TEXT,
    updated_at TIMESTAMPTZ,
    search_document TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', coalesce(article, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(name, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(category, '')), 'B') ||
        setweight(to_tsvector('simple', coalesce(attributes::text, '')), 'C')
    ) STORED
);

CREATE INDEX IF NOT EXISTS products_search_document_gin
    ON products USING GIN (search_document);
CREATE INDEX IF NOT EXISTS products_article_idx ON products (article);
CREATE INDEX IF NOT EXISTS products_category_idx ON products (category);
CREATE INDEX IF NOT EXISTS products_attributes_gin ON products USING GIN (attributes jsonb_path_ops);
"""


UPSERT_SQL = """
INSERT INTO products (
    id, article, name, category, attributes, certificate_links,
    price, warehouse_stocks, product_url, updated_at
) VALUES (
    %(id)s, %(article)s, %(name)s, %(category)s, %(attributes)s,
    %(certificate_links)s, %(price)s, %(warehouse_stocks)s,
    %(product_url)s, %(updated_at)s
)
ON CONFLICT (id) DO UPDATE SET
    article = EXCLUDED.article,
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    attributes = EXCLUDED.attributes,
    certificate_links = EXCLUDED.certificate_links,
    price = EXCLUDED.price,
    warehouse_stocks = EXCLUDED.warehouse_stocks,
    product_url = EXCLUDED.product_url,
    updated_at = EXCLUDED.updated_at
RETURNING *
"""


class ProductCatalog:
    """Async PostgreSQL repository. It does not own/close the supplied pool."""

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self.pool = pool

    @classmethod
    async def connect(cls, database_url: str, *, min_size: int = 1, max_size: int = 5) -> ProductCatalog:
        pool = AsyncConnectionPool(
            conninfo=database_url,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row},
            open=False,
        )
        await pool.open()
        return cls(pool)

    async def close(self) -> None:
        await self.pool.close()

    async def initialize(self) -> None:
        """Create catalog table and indexes; normally run as a deployment migration."""
        async with self.pool.connection() as conn:
            await conn.execute(SCHEMA_SQL)

    async def upsert_product(self, product: EktProduct) -> dict[str, Any]:
        values = product.model_dump(mode="json")
        async with self.pool.connection() as conn:
            cursor = await conn.execute(UPSERT_SQL, values)
            return await cursor.fetchone()

    async def upsert_products(self, products: list[EktProduct]) -> int:
        if not products:
            return 0
        values = [product.model_dump(mode="json") for product in products]
        async with self.pool.connection() as conn:
            await conn.executemany(UPSERT_SQL, values)
        return len(values)

    async def get_product(self, product_id: str) -> dict[str, Any] | None:
        async with self.pool.connection() as conn:
            cursor = await conn.execute("SELECT * FROM products WHERE id = %s", (product_id,))
            return await cursor.fetchone()

    async def search(
        self,
        query: str,
        *,
        category: str | None = None,
        attributes: dict[str, Any] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search articles/names and optionally filter category/JSONB attributes."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        normalized = query.strip()
        if not normalized and not category and not attributes:
            return []
        async with self.pool.connection() as conn:
            if normalized:
                sql = """
                    SELECT *, ts_rank(search_document, plainto_tsquery('simple', %s)) AS rank
                    FROM products
                    WHERE search_document @@ plainto_tsquery('simple', %s)
                      AND (%s IS NULL OR category = %s)
                      AND (%s::jsonb IS NULL OR attributes @> %s::jsonb)
                    ORDER BY rank DESC, name
                    LIMIT %s
                """
                params = (
                    normalized, normalized, category, category,
                    _json_param(attributes), _json_param(attributes), limit,
                )
            else:
                sql = """
                    SELECT * FROM products
                    WHERE (%s IS NULL OR category = %s)
                      AND (%s::jsonb IS NULL OR attributes @> %s::jsonb)
                    ORDER BY name LIMIT %s
                """
                params = (category, category, _json_param(attributes), _json_param(attributes), limit)
            cursor = await conn.execute(sql, params)
            return await cursor.fetchall()


def _json_param(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
