import pytest
from pydantic import ValidationError

from app.config.settings import Settings
from app.main import app


def test_openapi_exposes_stable_browser_operation_ids_and_typed_chat_payloads() -> None:
    schema = app.openapi()

    assert schema["info"]["version"] == "1.1.0"
    assert schema["paths"]["/api/chat/sessions"]["post"]["operationId"] == "create_chat_session"
    assert schema["paths"]["/api/chat/sessions/{session_id}/messages"]["post"]["operationId"] == "send_chat_message"
    assert schema["paths"]["/api/chat/sessions/{session_id}/offers/{offer_id}/confirm"]["post"]["operationId"] == "confirm_pending_offer"

    chat_reply = schema["components"]["schemas"]["ChatReply"]["properties"]
    assert chat_reply["candidates"]["items"] == {"$ref": "#/components/schemas/CatalogCandidate"}
    discriminator = chat_reply["current_data"]["anyOf"][0]["discriminator"]
    assert discriminator["propertyName"] == "kind"
    assert set(discriminator["mapping"]) == {"current_availability", "fresh_product"}

    validation_response = schema["paths"]["/api/chat/sessions/{session_id}/messages"]["post"]["responses"]["422"]
    assert validation_response["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}


def test_cors_configuration_supports_multiple_explicit_origins_and_rejects_wildcards() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://test:test@localhost:5432/test",
        cors_allowed_origins="https://shop.example.kz, https://admin.example.kz/",
    )

    assert settings.cors_origins == ("https://shop.example.kz", "https://admin.example.kz")

    with pytest.raises(ValidationError, match="Wildcard CORS origins are not allowed"):
        Settings(
            database_url="postgresql+psycopg://test:test@localhost:5432/test",
            cors_allowed_origins="*",
        )
