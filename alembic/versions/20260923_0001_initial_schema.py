"""Initial chat service schema.

Revision ID: 20260923_0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260923_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_key", sa.String(128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("context", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chat_sessions_expires_at", "chat_sessions", ["expires_at"])

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_messages_session_created", "messages", ["session_id", "created_at"])

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("article", sa.String(128), nullable=False, unique=True),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("characteristics", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("price", sa.Numeric(14, 2)),
        sa.Column("search_vector", postgresql.TSVECTOR(), server_default=sa.text("''::tsvector"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_products_search_vector", "products", ["search_vector"], postgresql_using="gin")
    op.create_index("ix_products_characteristics", "products", ["characteristics"], postgresql_using="gin", postgresql_ops={"characteristics": "jsonb_path_ops"})
    op.execute("""
        CREATE FUNCTION products_search_vector_update() RETURNS trigger AS $$
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
    op.execute("CREATE TRIGGER trg_products_search_vector_update BEFORE INSERT OR UPDATE ON products FOR EACH ROW EXECUTE FUNCTION products_search_vector_update()")

    op.create_table(
        "pending_offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pending_offers_session_id", "pending_offers", ["session_id"])
    op.create_index("ix_pending_offers_expires_at", "pending_offers", ["expires_at"])

    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope", sa.String(128), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("response_payload", postgresql.JSONB()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),
    )
    op.create_index("ix_idempotency_keys_expires_at", "idempotency_keys", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_keys_expires_at", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
    op.drop_index("ix_pending_offers_expires_at", table_name="pending_offers")
    op.drop_index("ix_pending_offers_session_id", table_name="pending_offers")
    op.drop_table("pending_offers")
    op.execute("DROP TRIGGER IF EXISTS trg_products_search_vector_update ON products")
    op.execute("DROP FUNCTION IF EXISTS products_search_vector_update()")
    op.drop_index("ix_products_characteristics", table_name="products")
    op.drop_index("ix_products_search_vector", table_name="products")
    op.drop_table("products")
    op.drop_index("ix_messages_session_created", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_chat_sessions_expires_at", table_name="chat_sessions")
    op.drop_table("chat_sessions")
