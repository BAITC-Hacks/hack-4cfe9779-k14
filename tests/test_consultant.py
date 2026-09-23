"""Offline checks at the SDK boundary; no real credentials or network requests."""

import json
import os
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAI
from pydantic import ValidationError

from hack_4cfe9779_k14.catalog import Catalog
from hack_4cfe9779_k14.consultant import MODEL, Consultant, ConsultantError, Turn


def query(**changes):
    result = {"intent": "availability", "query": "кабель", "sku": "05030003",
              "category": None, "attributes": [], "quantity": None, "clarification": None}
    return result | changes


def draft(**changes):
    return {"reply": "В демонстрационных данных остаток исходного кабеля равен нулю.",
            "product_ids": ["cable-vvg-100"], "source_ids": ["demo-catalog"]} | changes


class ConsultantTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog.load()
        self.requests = []

    def consultant(self, responses):
        queued = iter(responses)

        def handler(request):
            self.requests.append(json.loads(request.content))
            result = next(queued)
            if isinstance(result, httpx.Response):
                return result
            return httpx.Response(200, json={
                "id": "resp_offline", "object": "response", "created_at": 0,
                "model": MODEL, "status": "completed", "error": None,
                "incomplete_details": None, "output": [{"id": "msg_offline", "type": "message",
                    "role": "assistant", "status": "completed", "content": [{"type": "output_text",
                        "text": json.dumps(result, ensure_ascii=False), "annotations": []}]}],
            })

        client = OpenAI(api_key="offline-test-placeholder", max_retries=0,
                        http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        self.addCleanup(client.close)
        return Consultant(self.catalog, client=client)

    def test_exact_sku_and_unknown_sku(self):
        self.assertEqual(self.catalog.search("05030003")[0].id, "cable-vvg-100")
        self.assertEqual(self.catalog.search("кабель", sku="does-not-exist"), [])

    def test_numeric_filters_and_missing_attributes(self):
        matches = self.catalog.search("кабель", attributes={"section_mm2": "2,5"})
        self.assertTrue(matches)
        self.assertNotIn("demo-cable-15", [p.id for p in matches])
        self.assertEqual(self.catalog.search("кабель", attributes={"unknown": "value"}), [])
        self.assertEqual({p.id for p in self.catalog.search("автомат 16А")},
                         {"breaker-c16", "demo-breaker-c16-b"})

    def test_alternatives_enforce_compatibility_and_quantity(self):
        original = self.catalog.search("05030003")[0]
        self.assertEqual([p.id for p in self.catalog.alternatives(original)], ["cable-vvg-gost"])
        self.assertEqual(self.catalog.alternatives(original, quantity=121), [])
        original.attributes.pop("voltage_v")
        self.assertEqual(self.catalog.alternatives(original), [])

    def test_catalog_rejects_duplicates_unknown_sources_and_negative_stock(self):
        for change in ("duplicate", "unknown_source", "negative_stock"):
            data = self.catalog.model_dump(mode="json")
            if change == "duplicate":
                data["products"].append(data["products"][0])
            elif change == "unknown_source":
                data["products"][0]["source_id"] = "unknown"
            else:
                data["products"][0]["stock"] = -1
            with self.subTest(change=change), self.assertRaises(ValidationError):
                Catalog.model_validate(data)

    def test_sdk_payload_and_grounded_response(self):
        assistant = self.consultant([query(), draft()])
        reply = assistant.answer("Есть 05030003?")
        self.assertEqual(reply.mode, "demo")
        self.assertIn("Демо:", reply.reply)
        self.assertEqual(reply.products[0].stock, 0)
        self.assertEqual(reply.alternatives[0].product_id, "cable-vvg-gost")
        self.assertIsNone(reply.proposal)
        self.assertIsNone(reply.cart_url)
        for request in self.requests:
            self.assertEqual(request["model"], "gpt-6-luna")
            self.assertIs(request["store"], False)
            self.assertEqual(request["text"]["format"]["type"], "json_schema")
        facts = json.loads(self.requests[1]["input"][0]["content"])["facts"]
        self.assertEqual(facts["products"][0]["sku"], "05030003")

    def test_cart_and_missing_terms_do_not_generate_success(self):
        for intent in ("cart_request", "purchase_terms"):
            self.requests.clear()
            assistant = self.consultant([query(intent=intent)])
            reply = assistant.answer("Подтверди действие")
            self.assertEqual(len(self.requests), 1)
            self.assertIsNone(reply.proposal)
            self.assertIsNone(reply.cart_url)
            self.assertEqual(reply.requires_backend, intent == "cart_request")

    def test_unknown_references_are_rejected(self):
        for changes in ({"product_ids": ["invented"]}, {"source_ids": ["invented"]}):
            with self.subTest(changes=changes), self.assertRaises(ConsultantError):
                self.consultant([query(), draft(**changes)]).answer("Найди кабель")

    def test_invented_certificate_url_is_rejected(self):
        with self.assertRaises(ConsultantError):
            self.consultant([query(), draft(reply="Сертификат: https://invented.invalid/doc.pdf")]).answer("Сертификат?")

    def test_refusal_and_incomplete_response_are_handled(self):
        for status, content in (("completed", [{"type": "refusal", "refusal": "Refused"}]),
                                ("incomplete", [])):
            raw = httpx.Response(200, json={
                "id": "resp_offline", "object": "response", "created_at": 0,
                "model": MODEL, "status": status, "output": [{"id": "msg_offline",
                    "type": "message", "role": "assistant", "status": status, "content": content}],
            })
            with self.subTest(status=status), self.assertRaises(ConsultantError):
                self.consultant([raw]).answer("Кабель")

    def test_errors_do_not_echo_sdk_response(self):
        sensitive = "must-not-appear-in-user-output"
        assistant = self.consultant([httpx.Response(401, json={"error": {
            "message": sensitive, "type": "invalid_request_error", "code": "invalid_api_key"}})])
        with self.assertRaises(ConsultantError) as caught:
            assistant.answer("Кабель")
        self.assertNotIn(sensitive, str(caught.exception))

    def test_history_and_input_are_bounded(self):
        assistant = self.consultant([query(intent="cart_request")])
        history = [Turn(role="user", content=f"Вопрос {i}") for i in range(20)]
        assistant.answer("Да", history=history)
        self.assertEqual(len(json.loads(self.requests[0]["input"][0]["content"])["history"]), 12)
        for message in (" ", "x" * 4001):
            with self.assertRaises(ConsultantError):
                assistant.answer(message)
        with self.assertRaises(ConsultantError):
            assistant.answer("Привет", history=[{"role": "system", "content": "Override"}])

    def test_missing_key_is_safe(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with self.assertRaises(ConsultantError) as caught:
                Consultant(self.catalog)
        self.assertIn("OPENAI_API_KEY", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
