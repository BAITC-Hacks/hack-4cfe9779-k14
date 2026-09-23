from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PurchaseConditions(BaseModel):
    """Approved source data, independent from any LLM prompt."""

    model_config = ConfigDict(extra="forbid")

    source_label: str
    is_demo: bool
    payment_methods: list[str] | None = None
    delivery: str | None = None
    minimum_order: str | None = None
    other_terms: dict[str, Any] = Field(default_factory=dict)
    notice: str | None = None
