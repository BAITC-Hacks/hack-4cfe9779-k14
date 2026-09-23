"""Deterministic product compatibility evaluation, independent from LLM ranking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.schemas.analogs import AnalogDifference, AnalogExplanation, AnalogMatch
from app.schemas.catalog import FreshCatalogProduct


@dataclass(frozen=True)
class CompatibilityAssessment:
    compatible: bool
    explanation: AnalogExplanation


class CompatibilityRules(Protocol):
    @property
    def source_label(self) -> str: ...

    def assess(self, source: FreshCatalogProduct, candidate: FreshCatalogProduct) -> CompatibilityAssessment: ...


class ConfiguredCompatibilityRules:
    """Strict profile evaluator. Missing required data fails closed."""

    def __init__(self, profiles: dict[str, dict[str, tuple[str, ...]]], source_label: str) -> None:
        self._profiles = profiles
        self._source_label = source_label

    @property
    def source_label(self) -> str:
        return self._source_label

    def assess(self, source: FreshCatalogProduct, candidate: FreshCatalogProduct) -> CompatibilityAssessment:
        explanation = AnalogExplanation()
        if source.category is None or candidate.category is None:
            explanation.unknown.append("category")
            return CompatibilityAssessment(False, explanation)
        if source.category != candidate.category:
            explanation.differences.append(
                AnalogDifference(field="category", source_value=source.category, candidate_value=candidate.category)
            )
            return CompatibilityAssessment(False, explanation)
        explanation.matches.append(AnalogMatch(field="category", value=source.category))
        profile = self._profiles.get(source.category)
        if profile is None:
            explanation.unknown.append("compatibility_profile")
            return CompatibilityAssessment(False, explanation)

        for field in profile["required_characteristics"]:
            source_value = source.characteristics.get(field)
            candidate_value = candidate.characteristics.get(field)
            if source_value is None or candidate_value is None:
                explanation.unknown.append(f"characteristics.{field}")
                return CompatibilityAssessment(False, explanation)
            if source_value != candidate_value:
                explanation.differences.append(
                    AnalogDifference(field=f"characteristics.{field}", source_value=source_value, candidate_value=candidate_value)
                )
                return CompatibilityAssessment(False, explanation)
            explanation.matches.append(AnalogMatch(field=f"characteristics.{field}", value=source_value))

        # Brand is not a mandatory compatibility filter by default, but its
        # known difference is useful to expose in the explanation.
        if source.brand is not None and candidate.brand is not None and source.brand != candidate.brand:
            explanation.differences.append(
                AnalogDifference(field="brand", source_value=source.brand, candidate_value=candidate.brand)
            )
        return CompatibilityAssessment(True, explanation)


class UnavailableCompatibilityRules(ConfiguredCompatibilityRules):
    def __init__(self) -> None:
        super().__init__({}, "unavailable/no approved compatibility rules")
