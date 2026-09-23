from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.catalog import FreshCatalogProduct


class AnalogMatch(BaseModel):
    field: str
    value: Any


class AnalogDifference(BaseModel):
    field: str
    source_value: Any
    candidate_value: Any


class AnalogExplanation(BaseModel):
    matches: list[AnalogMatch] = Field(default_factory=list)
    differences: list[AnalogDifference] = Field(default_factory=list)
    unknown: list[str] = Field(default_factory=list)


class AnalogSuggestion(BaseModel):
    product: FreshCatalogProduct
    score: float
    explanation: AnalogExplanation


class AnalogSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_article: str
    source_in_stock: bool | None
    rules_source: str
    candidates: list[AnalogSuggestion] = Field(default_factory=list)
