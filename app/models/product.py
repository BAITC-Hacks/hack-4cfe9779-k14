import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Numeric, String, Text, func, text
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
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    characteristics: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric(14, 2))
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        server_default=text("''::tsvector"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
