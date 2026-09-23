"""Validated catalog snapshots and deterministic retrieval, independent of OpenAI."""

import re
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class Source(Record):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    url: HttpUrl | None = None
    as_of: datetime | None = None


class Certificate(Record):
    title: str = Field(min_length=1, max_length=200)
    url: HttpUrl


class Product(Record):
    id: str = Field(min_length=1, max_length=100)
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=300)
    category: str = Field(min_length=1, max_length=100)
    price: float | None = Field(default=None, ge=0)
    currency: str = "KZT"
    stock: float | None = Field(default=None, ge=0)
    unit: str = Field(min_length=1, max_length=30)
    specs: list[str] = Field(default_factory=list, max_length=30)
    attributes: dict[str, str] = Field(default_factory=dict)
    art: Literal["cable", "breaker", "lamp", "tray"]
    certificates: list[Certificate] = Field(default_factory=list, max_length=10)
    source_id: str


class PurchaseTerm(Record):
    topic: Literal["payment", "delivery", "minimum_order"]
    text: str = Field(min_length=1, max_length=5000)
    source_id: str


def normalize(value: str) -> str:
    value = value.casefold().replace("ё", "е")
    value = re.sub(r"(?<=\d),(?=\d)", ".", value)
    value = re.sub(r"(?<=\d)\s*[хx×]\s*(?=\d)", "x", value)
    value = re.sub(r"(?<=\d)(?=[а-я])", " ", value)
    return " ".join(value.split())


def sku_key(value: str) -> str:
    return re.sub(r"[\s_-]", "", normalize(value))


class Catalog(Record):
    mode: Literal["demo", "snapshot"]
    sources: list[Source] = Field(min_length=1, max_length=1000)
    products: list[Product] = Field(min_length=1, max_length=10000)
    purchase_terms: list[PurchaseTerm] = Field(default_factory=list, max_length=50)
    # These keys must be reviewed by the partner for each real product category.
    compatibility_keys: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_references(self) -> "Catalog":
        for values in ([s.id for s in self.sources], [p.id for p in self.products],
                       [sku_key(p.sku) for p in self.products]):
            if len(values) != len(set(values)):
                raise ValueError("Идентификаторы источников, товаров и артикулы должны быть уникальны")
        source_ids = {source.id for source in self.sources}
        if any(item.source_id not in source_ids for item in [*self.products, *self.purchase_terms]):
            raise ValueError("Неизвестный источник данных")
        return self

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Catalog":
        resource = Path(path) if path else files(__package__).joinpath("demo_catalog.json")
        with resource.open("rb") as stream:
            data = stream.read(10 * 1024 * 1024 + 1)
        if len(data) > 10 * 1024 * 1024:
            raise ValueError("Каталог должен быть не больше 10 МБ")
        return cls.model_validate_json(data)

    def search(self, query: str, *, sku: str | None = None,
               category: str | None = None, attributes: dict[str, str] | None = None,
               limit: int = 5) -> list[Product]:
        """Exact SKU wins; requested attributes are hard filters, not ranking hints."""
        if not 1 <= limit <= 10:
            raise ValueError("Допустимое число результатов: 1–10")
        wanted_sku = sku_key(sku) if sku else None
        if wanted_sku is None and any(sku_key(query) == sku_key(p.sku) for p in self.products):
            wanted_sku = sku_key(query)
        tokens = set(re.findall(r"[\w.]+", normalize(query)))
        tokens -= {"есть", "ли", "нужен", "нужны", "покажи", "найди", "товар", "в", "на", "и"}
        ranked = []
        # ponytail: linear scan for <=10,000 demo/snapshot products; use backend SQL at scale.
        for product in self.products:
            if wanted_sku and sku_key(product.sku) != wanted_sku:
                continue
            if category and normalize(category) != normalize(product.category):
                continue
            if any(normalize(product.attributes.get(k, "")) != normalize(v)
                   for k, v in (attributes or {}).items()):
                continue
            words = set(re.findall(r"[\w.]+", normalize(" ".join(
                [product.name, product.category, product.sku, *product.specs]))))
            if not wanted_sku and any(any(c.isdigit() for c in token) and token not in words for token in tokens):
                continue
            score = sum(1 for token in tokens if token in words or (
                len(token) >= 4 and token.isalpha() and any(word.startswith(token) for word in words)))
            if wanted_sku or score or (not tokens and (category or attributes)):
                ranked.append((100 if wanted_sku else score, product))
        return [p for _, p in sorted(ranked, key=lambda pair: (-pair[0], pair[1].sku))[:limit]]

    def alternatives(self, original: Product, quantity: float | None = None) -> list[Product]:
        keys = self.compatibility_keys.get(original.category, [])
        if not keys or any(not original.attributes.get(key) for key in keys):
            return []
        matches = []
        for candidate in self.products:
            if candidate.id == original.id or candidate.category != original.category:
                continue
            if candidate.unit != original.unit or candidate.stock is None or candidate.stock <= 0:
                continue
            if quantity is not None and candidate.stock < quantity:
                continue
            if all(candidate.attributes.get(key) and
                   normalize(candidate.attributes[key]) == normalize(original.attributes[key])
                   for key in keys):
                matches.append(candidate)
        return matches[:3]
