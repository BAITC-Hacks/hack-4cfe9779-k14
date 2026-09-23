"""Persist the server-owned cart context for each pending offer.

Revision ID: 20260923_0008
Revises: 20260923_0007
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260923_0008"
down_revision = "20260923_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pending_offers",
        sa.Column(
            "cart_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column("pending_offers", "cart_context", server_default=None)


def downgrade() -> None:
    op.drop_column("pending_offers", "cart_context")
