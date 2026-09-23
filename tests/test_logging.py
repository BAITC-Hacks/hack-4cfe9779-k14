import json
import logging

from app.config.logging import JsonFormatter


def test_json_formatter_keeps_structured_fields() -> None:
    record = logging.LogRecord("test", logging.WARNING, "", 0, "failed", (), None)
    record.event = "ekt_api_failure"
    record.operation = "list_products"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "ekt_api_failure"
    assert payload["operation"] == "list_products"
    assert payload["message"] == "failed"
