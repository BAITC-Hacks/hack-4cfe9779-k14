"""Add category, certificates and source fields to products.

Revision ID: 20260923_0006
Revises: 20260923_0005
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260923_0006"
down_revision = "20260923_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("category", sa.String(256)))
    op.add_column("products", sa.Column("certificates", postgresql.JSONB()))
    op.add_column("products", sa.Column("source_fields", postgresql.JSONB()))
    op.create_index("ix_products_category", "products", ["category"])


def downgrade() -> None:
    op.drop_index("ix_products_category", table_name="products")
    op.drop_column("products", "source_fields")
    op.drop_column("products", "certificates")
    op.drop_column("products", "category")
