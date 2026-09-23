"""Add catalog cache and brand fields.

Revision ID: 20260923_0002
Revises: 20260923_0001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260923_0002"
down_revision = "20260923_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("products", "price", new_column_name="cached_price")
    op.add_column("products", sa.Column("external_id", sa.String(128)))
    op.add_column("products", sa.Column("brand", sa.String(256)))
    op.add_column("products", sa.Column("cached_stock_by_location", postgresql.JSONB()))
    op.add_column("products", sa.Column("cached_available", sa.Boolean()))
    op.create_unique_constraint("uq_products_external_id", "products", ["external_id"])
    op.create_index("ix_products_brand", "products", ["brand"])
    op.execute("""
        CREATE OR REPLACE FUNCTION products_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('simple', coalesce(NEW.article, '')), 'A') ||
                setweight(to_tsvector('simple', coalesce(NEW.name, '')), 'A') ||
                setweight(to_tsvector('simple', coalesce(NEW.brand, '')), 'A') ||
                setweight(to_tsvector('simple', coalesce(NEW.description, '')), 'B') ||
                setweight(to_tsvector('simple', coalesce(NEW.characteristics::text, '')), 'C');
            NEW.updated_at := now();
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION products_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('simple', coalesce(NEW.article, '')), 'A') ||
                setweight(to_tsvector('simple', coalesce(NEW.name, '')), 'A') ||
                setweight(to_tsvector('simple', coalesce(NEW.description, '')), 'B') ||
                setweight(to_tsvector('simple', coalesce(NEW.characteristics::text, '')), 'C');
            NEW.updated_at := now();
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
    """)
    op.drop_index("ix_products_brand", table_name="products")
    op.drop_constraint("uq_products_external_id", "products", type_="unique")
    op.drop_column("products", "cached_available")
    op.drop_column("products", "cached_stock_by_location")
    op.drop_column("products", "brand")
    op.drop_column("products", "external_id")
    op.alter_column("products", "cached_price", new_column_name="price")
