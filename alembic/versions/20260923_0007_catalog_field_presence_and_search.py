"""Preserve source field presence and include catalog fields in text search.

Revision ID: 20260923_0007
Revises: 20260923_0006
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260923_0007"
down_revision = "20260923_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "source_field_presence",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.execute("""
        CREATE OR REPLACE FUNCTION products_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('simple', coalesce(NEW.article, '')), 'A') ||
                setweight(to_tsvector('simple', coalesce(NEW.name, '')), 'A') ||
                setweight(to_tsvector('simple', coalesce(NEW.brand, '')), 'A') ||
                setweight(to_tsvector('simple', coalesce(NEW.category, '')), 'A') ||
                setweight(to_tsvector('simple', coalesce(NEW.description, '')), 'B') ||
                setweight(to_tsvector('simple', coalesce(NEW.characteristics::text, '')), 'C') ||
                setweight(to_tsvector('simple', coalesce(NEW.source_fields::text, '')), 'C');
            NEW.updated_at := now();
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
    """)
    op.execute("UPDATE products SET updated_at = now()")


def downgrade() -> None:
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
    op.drop_column("products", "source_field_presence")
