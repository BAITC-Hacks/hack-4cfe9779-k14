"""Add expiry to normalized chat attachment data.

Revision ID: 20260923_0005
Revises: 20260923_0004
"""
from alembic import op
import sqlalchemy as sa

revision = "20260923_0005"
down_revision = "20260923_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_attachments",
        sa.Column("expires_at", sa.DateTime(timezone=True), server_default=sa.text("now() + interval '1 day'"), nullable=False),
    )
    op.create_index("ix_chat_attachments_expires_at", "chat_attachments", ["expires_at"])
    op.alter_column("chat_attachments", "expires_at", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_chat_attachments_expires_at", table_name="chat_attachments")
    op.drop_column("chat_attachments", "expires_at")
