"""Persist normalized chat attachment references.

Revision ID: 20260923_0004
Revises: 20260923_0003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260923_0004"
down_revision = "20260923_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("document_type", sa.String(32), nullable=False),
        sa.Column("extracted_text", sa.Text(), server_default="", nullable=False),
        sa.Column("tables", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("warnings", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chat_attachments_session_id", "chat_attachments", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_attachments_session_id", table_name="chat_attachments")
    op.drop_table("chat_attachments")
