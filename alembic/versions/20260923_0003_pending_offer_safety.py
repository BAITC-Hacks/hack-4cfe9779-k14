"""Add explicit pending-offer confirmation fields.

Revision ID: 20260923_0003
Revises: 20260923_0002
"""
from alembic import op
import sqlalchemy as sa

revision = "20260923_0003"
down_revision = "20260923_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pending_offers", sa.Column("product_identifier", sa.String(128), nullable=False))
    op.add_column("pending_offers", sa.Column("article", sa.String(128), nullable=False))
    op.add_column("pending_offers", sa.Column("quantity", sa.Integer(), nullable=False))
    op.add_column("pending_offers", sa.Column("price_at_offer", sa.Numeric(14, 2), nullable=False))
    op.add_column("pending_offers", sa.Column("status", sa.String(32), server_default="pending", nullable=False))
    op.create_index("ix_pending_offers_session_status", "pending_offers", ["session_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_pending_offers_session_status", table_name="pending_offers")
    op.drop_column("pending_offers", "status")
    op.drop_column("pending_offers", "price_at_offer")
    op.drop_column("pending_offers", "quantity")
    op.drop_column("pending_offers", "article")
    op.drop_column("pending_offers", "product_identifier")
