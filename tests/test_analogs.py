from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.schemas.catalog import CatalogCandidate, CatalogSearchResponse, CurrentAvailability, FreshCatalogProduct
from app.schemas.chat import ChatMessageCreate, ChatRole
from app.services.analogs import AnalogService
from app.services.chat import ChatService
from app.services.errors import ResourceNotFound

pytestmark = pytest.mark.asyncio


def product(
    article: str,
    name: str,
    *,
    available: bool | None,
    characteristics: dict | None = None,
    category: str | None = "Кабель и провод",
    brand: str | None = "DemoCable",
) -> FreshCatalogProduct:
    return FreshCatalogProduct(
        article=article,
        external_id=f"external-{article}",
        name=name,
        category=category,
        brand=brand,
        characteristics=characteristics if characteristics is not None else {
            "material": "медь", "cores": 3, "cross_section_mm2": 1.5,
        },
        cached_price=Decimal("100.00"),
        cached_stock_by_location={"Алматы": 3} if available else {"Алматы": 0},
        cached_available=available,
        certificates=[],
        source_field_presence={"characteristics": True, "certificates": True},
    )


def candidate(item: FreshCatalogProduct) -> CatalogCandidate:
    return CatalogCandidate(id=uuid4(), **item.model_dump(exclude={"fresh"}))


class InMemoryCatalog:
    def __init__(self, products: list[FreshCatalogProduct]) -> None:
        self.products = {item.article: item for item in products}

    async def search_candidates(self, query, *, characteristics=None, limit=20):
        del characteristics
        if query in self.products:
            return CatalogSearchResponse(candidates=[candidate(self.products[query])], match_type="exact_article")
        values = [item for item in self.products.values() if item.category == query][:limit]
        return CatalogSearchResponse(candidates=[candidate(item) for item in values], match_type="full_text")

    async def get_fresh_product(self, article: str) -> FreshCatalogProduct:
        try:
            return self.products[article]
        except KeyError as exc:
            raise ResourceNotFound("missing") from exc

    async def get_current_availability(self, article: str) -> CurrentAvailability:
        item = await self.get_fresh_product(article)
        return CurrentAvailability(
            article=item.article,
            price=item.cached_price,
            stock_by_location=item.cached_stock_by_location,
            available=item.cached_available,
            current=True,
        )


async def test_compatible_candidate_survives_before_ranking_and_similar_incompatible_candidates_do_not() -> None:
    source = product("SRC-1", "Кабель ВВГнг-LS 3x1,5", available=False)
    good = product("ALT-1", "Кабель ВВГнг-LS 3x1,5 замена", available=True, brand="OtherBrand")
    similar_name_but_two_cores = product(
        "BAD-CORES", "Кабель ВВГнг-LS 3x1,5 замена", available=True,
        characteristics={"material": "медь", "cores": 2, "cross_section_mm2": 1.5},
    )
    different_material = product(
        "BAD-MATERIAL", "Кабель ВВГнг-LS 3x1,5", available=True,
        characteristics={"material": "алюминий", "cores": 3, "cross_section_mm2": 1.5},
    )

    result = await AnalogService(InMemoryCatalog([source, good, similar_name_but_two_cores, different_material])).find_analogs("SRC-1")

    assert result.source_in_stock is False
    assert [item.product.article for item in result.candidates] == ["ALT-1"]
    explanation = result.candidates[0].explanation
    assert {item.field for item in explanation.matches} == {
        "category", "characteristics.material", "characteristics.cores", "characteristics.cross_section_mm2",
    }
    assert [(item.field, item.source_value, item.candidate_value) for item in explanation.differences] == [
        ("brand", "DemoCable", "OtherBrand")
    ]
    assert explanation.unknown == []


async def test_multiple_compatible_candidates_are_ranked_only_after_filters() -> None:
    source = product("SRC-1", "Кабель ВВГнг-LS 3x1,5", available=False)
    closer = product("ALT-CLOSER", "Кабель ВВГнг-LS 3x1,5", available=True)
    farther = product("ALT-FARTHER", "Медный кабель 3x1,5", available=True)
    rejected = product(
        "BAD-SECTION", "Кабель ВВГнг-LS 3x1,5", available=True,
        characteristics={"material": "медь", "cores": 3, "cross_section_mm2": 2.5},
    )

    result = await AnalogService(InMemoryCatalog([source, farther, rejected, closer])).find_analogs("SRC-1")

    assert [item.product.article for item in result.candidates] == ["ALT-CLOSER", "ALT-FARTHER"]
    assert all(item.product.article != "BAD-SECTION" for item in result.candidates)
    assert result.candidates[0].score > result.candidates[1].score


async def test_missing_critical_characteristic_fails_closed_and_no_analog_is_returned() -> None:
    source = product("SRC-1", "Кабель ВВГнг-LS 3x1,5", available=False)
    missing_section = product(
        "UNKNOWN-SECTION", "Кабель ВВГнг-LS 3x1,5", available=True,
        characteristics={"material": "медь", "cores": 3},
    )

    result = await AnalogService(InMemoryCatalog([source, missing_section])).find_analogs("SRC-1")

    assert result.candidates == []


async def test_missing_source_critical_characteristic_and_no_profile_never_infer_compatibility() -> None:
    missing_source_data = product(
        "SRC-MISSING", "Кабель", available=False, characteristics={"material": "медь", "cores": 3},
    )
    candidate_item = product("ALT-1", "Кабель", available=True)
    no_category = product("SRC-NO-CATEGORY", "Кабель", available=False, category=None)

    service = AnalogService(InMemoryCatalog([missing_source_data, candidate_item, no_category]))

    assert (await service.find_analogs("SRC-MISSING")).candidates == []
    assert (await service.find_analogs("SRC-NO-CATEGORY")).candidates == []


class SessionRepository:
    def __init__(self) -> None:
        self.session_id = uuid4()
        self.messages: list[SimpleNamespace] = []

    async def get_session(self, session_id: UUID):
        return SimpleNamespace(id=session_id) if session_id == self.session_id else None

    async def add_message(self, session_id, role, content, metadata=None):
        message = SimpleNamespace(
            id=uuid4(), session_id=session_id, role=role.value, content=content,
            created_at=datetime.now(timezone.utc), metadata_json=metadata or {},
        )
        self.messages.append(message)
        return message

    async def history(self, session_id, *, limit=None):
        values = [item for item in self.messages if item.session_id == session_id]
        return values[-limit:] if limit else values


class UnusedLLM:
    async def analyze(self, history, attachment_data=None):
        raise AssertionError("deterministic route should not invoke LLM")

    async def aclose(self):
        return None


async def test_out_of_stock_dialogue_offers_only_compatible_analogs() -> None:
    source = product("SRC-1", "Кабель ВВГнг-LS 3x1,5", available=False)
    good = product("ALT-1", "Кабель ВВГнг-LS 3x1,5 аналог", available=True)
    bad = product(
        "BAD-1", "Кабель ВВГнг-LS 3x1,5 аналог", available=True,
        characteristics={"material": "медь", "cores": 2, "cross_section_mm2": 1.5},
    )
    repository = SessionRepository()
    catalog = InMemoryCatalog([source, good, bad])
    service = ChatService(repository, catalog, UnusedLLM(), analogs=AnalogService(catalog))

    await service.send_message(repository.session_id, ChatMessageCreate(content="Найди SRC-1"))
    reply = await service.send_message(repository.session_id, ChatMessageCreate(content="А наличие?"))

    assert "нет в наличии" in reply.assistant_message.content
    assert [item.product.article for item in reply.analogs] == ["ALT-1"]
    assert "BAD-1" not in reply.assistant_message.content


async def test_zero_stock_without_availability_flag_still_allows_safe_analog_suggestion() -> None:
    source = product("SRC-1", "Кабель ВВГнг-LS 3x1,5", available=None)
    source = source.model_copy(update={"cached_stock_by_location": {"Алматы": 0}})
    good = product("ALT-1", "Кабель ВВГнг-LS 3x1,5 аналог", available=True)
    repository = SessionRepository()
    catalog = InMemoryCatalog([source, good])
    service = ChatService(repository, catalog, UnusedLLM(), analogs=AnalogService(catalog))

    await service.send_message(repository.session_id, ChatMessageCreate(content="Найди SRC-1"))
    reply = await service.send_message(repository.session_id, ChatMessageCreate(content="Остаток?"))

    assert [item.product.article for item in reply.analogs] == ["ALT-1"]


async def test_analog_request_reports_honestly_when_no_candidate_passes_filters() -> None:
    source = product("SRC-1", "Кабель ВВГнг-LS 3x1,5", available=False)
    incompatible = product(
        "BAD-1", "Кабель ВВГнг-LS 3x1,5", available=True,
        characteristics={"material": "алюминий", "cores": 3, "cross_section_mm2": 1.5},
    )
    repository = SessionRepository()
    catalog = InMemoryCatalog([source, incompatible])
    service = ChatService(repository, catalog, UnusedLLM(), analogs=AnalogService(catalog))

    reply = await service.send_message(repository.session_id, ChatMessageCreate(content="Найди аналог SRC-1"))

    assert reply.analogs == []
    assert "не найдено" in reply.assistant_message.content
