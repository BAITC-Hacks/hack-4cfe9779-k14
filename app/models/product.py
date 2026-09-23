import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Index, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_search_vector", "search_vector", postgresql_using="gin"),
        Index("ix_products_characteristics", "characteristics", postgresql_using="gin", postgresql_ops={"characteristics": "jsonb_path_ops"}),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(String(256), index=True)
    category: Mapped[str | None] = mapped_column(String(256), index=True)
    characteristics: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    cached_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    cached_stock_by_location: Mapped[dict | None] = mapped_column(JSONB)
    cached_available: Mapped[bool | None] = mapped_column(Boolean)
    # NULL means the source did not provide this field. An empty list means the
    # source explicitly reported that no certificates are attached.
    certificates: Mapped[list[dict] | None] = mapped_column(JSONB)
    # Preserve normalized-but-unmodelled source fields without making claims
    # about their meaning. NULL means no source payload was supplied.
    source_fields: Mapped[dict | None] = mapped_column(JSONB)
    source_field_presence: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        server_default=text("''::tsvector"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
