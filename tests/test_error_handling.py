from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.config.settings import get_settings


def test_validation_errors_have_the_public_error_shape() -> None:
    with TestClient(app) as client:
        response = client.get("/api/catalog/search", params={"limit": 1000})

    assert response.status_code == 422
    assert response.json() == {"code": "validation_error", "message": "Request validation failed"}


def test_widget_origin_is_allowed_for_browser_requests() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/api/chat/sessions",
            headers={
                "Origin": get_settings().widget_origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type, Idempotency-Key",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == get_settings().widget_origin
    assert "Idempotency-Key" in response.headers["access-control-allow-headers"]


def test_http_errors_do_not_expose_fastapi_detail_shape() -> None:
    @app.get("/_test_http_error")
    async def test_http_error() -> None:
        raise HTTPException(status_code=400, detail="internal validation detail")

    try:
        with TestClient(app) as client:
            response = client.get("/_test_http_error")
        assert response.status_code == 400
        assert response.json() == {"code": "http_error", "message": "Request could not be processed"}
    finally:
        app.router.routes.pop()
