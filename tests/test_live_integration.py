"""Offline contract tests based on observed EKT shapes and Responses SDK boundary."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from openai import AsyncOpenAI

from app.integrations.ekt_mapper import LiveEktResponseMapper
from app.integrations.catalog_adapter import EktCatalogAdapter
from app.integrations.ekt_client import EktProduct
from app.integrations.responses_consultant import ResponsesConsultant
from app.integrations.llm_client import LLMStructuredOutputError
from app.schemas.chat import ChatMessageView, ChatRole
from app.services.catalog import CatalogService
from app.services.dialogue_router import DeterministicDialogueRouter, DialogueContext
from app.services.errors import CatalogDataInvalid


def test_observed_ekt_response_preserves_unknown_and_conflicting_data():
    mapper = LiveEktResponseMapper()
    row = {"id": 515291, "article": "200300285_", "name": "Автомат 160А", "price": 64920,
           "quantity": 23, "stores": [{"id": 13, "name": "Алматы", "quantity": 5}],
           "properties": {"NOMINALNYY_TOK": "250 А", "TORGOVAYA_MARKA": "Legrand"},
           "url": "https://ekt.kz/catalog/nizkovoltnaya_apparatura/item/", "offers": []}
    product = mapper.parse_product_detail(row)
    assert product.article.endswith('_')
    assert product.stock_by_location == {"Алматы [13]": 5}
    assert product.attributes['NOMINALNYY_TOK'] == '250 А'  # Do not silently reconcile contradictory upstream facts.
    assert product.certificates is None
    assert product.source_field_presence['certificates'] is False
    listed = mapper.parse_products_page({"items": [{"id": 1, "article": "ярп4520", "name": "Лампа", "price": 0}]})[0]
    assert listed.price == 0 and listed.stock_by_location is None
    assert mapper.parse_product_detail(row | {"stores": [{"name": "A", "quantity": 1.5}]}).stock_by_location is None
    assert mapper.parse_product_detail(row | {"price": "NaN", "image": "https://evil.test/x"}).price is None
    assert mapper.parse_product_detail(row | {"image": "https://evil.test/x"}).source_fields['image'] is None
    with pytest.raises(ValueError):
        mapper.parse_products_page({"products": []})


@pytest.mark.asyncio
async def test_live_refresh_uses_indexed_id_and_rejects_wrong_detail():
    class Client:
        async def get_product_details(self, identifier):
            assert identifier == '515291'
            return EktProduct(id=identifier, article='wrong', name='Wrong')
    class Repository:
        async def find_by_article(self, article):
            return SimpleNamespace(external_id='515291')
    service = CatalogService(Repository(), EktCatalogAdapter(Client()))
    with pytest.raises(CatalogDataInvalid):
        await service.get_fresh_product('200300285_')


def test_router_preserves_real_ekt_sku_forms():
    router = DeterministicDialogueRouter()
    for article in ['200300285_', 'ярп4520', '05030003', 'DEMO-CABLE-VVG-3X2-5']:
        assert router.route(f'Наличие {article}', DialogueContext()).article == article


@pytest.mark.asyncio
async def test_responses_bridge_uses_shared_model_schemas_and_validates_sources():
    calls = []
    results = iter([
        {"intent": "cart_request", "query": "автомат", "sku": "200300285_", "category": None, "attributes": [], "quantity": 2, "clarification": None},
        {"reply": "Цена 64920 ₸", "product_ids": ["200300285_"], "source_ids": ["catalog:200300285_"]},
        {"reply": "Выдуманный товар", "product_ids": ["injected"], "source_ids": []},
    ])
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "resp_test", "object": "response", "created_at": 0,
            "model": "gpt-6-luna", "status": "completed", "output": [{"id": "msg_test", "type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": json.dumps(next(results)), "annotations": []}]}]})
    client = AsyncOpenAI(api_key='test-placeholder', http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    consultant = ResponsesConsultant(client=client)
    try:
        history = [ChatMessageView(id=uuid4(), role=ChatRole.USER, content='Добавь 2 автомата 200300285_', created_at=datetime.now(timezone.utc))]
        analysis = await consultant.analyze(history)
        assert analysis.intent == 'add_to_cart_request' and analysis.quantity == 2
        facts = {"products": [{"id": "200300285_", "price": 64920}], "sources": [{"id": "catalog:200300285_", "url": "https://ekt.kz/catalog/item/"}]}
        assert '64920' in await consultant.compose('Цена?', facts)
        with pytest.raises(LLMStructuredOutputError):
            await consultant.compose('Придумай товар', facts)
        assert all(call['store'] is False and call['model'] == 'gpt-6-luna' for call in calls)
        assert all('tools' not in call for call in calls)
        assert '200300285_' in calls[0]['input'][0]['content']
    finally:
        await consultant.aclose()


@pytest.mark.asyncio
async def test_chat_composes_from_fresh_facts_without_analogs():
    from test_chat_service import FakeChatRepository, ProposalCatalog
    from app.schemas.chat import ChatMessageCreate
    from app.services.chat import ChatService
    class Composer:
        async def compose(self, message, facts):
            assert facts["products"][0]["price"] == 10
            assert facts["alternatives"] == []
            return "Цена по каталогу: 10."
    repository = FakeChatRepository()
    service = ChatService(repository, ProposalCatalog(), Composer())
    result = await service.send_message(repository.session_id, ChatMessageCreate(content="Цена A-1"))
    assert result.assistant_message.content == "Цена по каталогу: 10."
    assert result.pending_offer is None


def test_local_file_parser_preserves_cyrillic_article():
    from app.services.attachment_parser import AttachmentItemParser
    from app.schemas.attachments import AttachmentResult, DocumentType
    result = AttachmentResult(filename="test.txt", mime_type="text/plain", document_type=DocumentType.DOCX,
                              text="Артикул: ярп4520 Количество: 2")
    item = AttachmentItemParser().parse(uuid4(), result)[0]
    assert item.article == "ярп4520" and item.quantity == 2
    assert CatalogService._looks_like_sku("ярп4520")
