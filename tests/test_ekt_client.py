import logging
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.config.settings import get_settings
from app.integrations.ekt_client import (
    EktAuthenticationError,
    EktClient,
    EktClientRequestError,
    EktConnectionError,
    EktDataUnavailableError,
    EktInvalidJsonError,
    EktNotFoundError,
    EktProduct,
    EktProductNotFoundError,
    EktResponseFormatError,
    EktServerError,
    EktStockCheck,
    EktTimeoutError,
)

pytestmark = pytest.mark.asyncio


class TestMapper:
    """Mock API format used by tests, not asserted to be EKT's real schema."""

    def parse_products_page(self, payload: Any) -> list[EktProduct]:
        return [EktProduct.model_validate(row) for row in payload]

    def parse_product_detail(self, payload: Any) -> EktProduct:
        return EktProduct.model_validate(payload)


def setup_settings(monkeypatch: pytest.MonkeyPatch, *, retries: int = 1) -> None:
    monkeypatch.setenv("EKT_API_USERNAME", "mock-user")
    monkeypatch.setenv("EKT_API_PASSWORD", "mock-password")
    monkeypatch.setenv("EKT_API_BASE_URL", "https://partner.invalid/api/")
    monkeypatch.setenv("EKT_READ_RETRY_COUNT", str(retries))
    monkeypatch.setenv("EKT_RETRY_BACKOFF_SECONDS", "0")
    get_settings.cache_clear()


def product(article: str = "A-1", **kwargs: Any) -> dict[str, Any]:
    return {"id": f"id-{article}", "article": article, "name": "Test product", **kwargs}


async def test_list_uses_basic_auth_and_documented_page_parameter(monkeypatch: pytest.MonkeyPatch) -> None:
    setup_settings(monkeypatch)
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[product()])

    async with EktClient(TestMapper(), transport=httpx.MockTransport(handler)) as client:
        results = await client.get_products_page(2)

    assert results[0].article == "A-1"
    assert seen[0].url.path == "/api/products"
    assert seen[0].url.params["page"] == "2"
    assert seen[0].headers["authorization"].startswith("Basic ")


async def test_details_price_and_stock_are_mapped_from_fresh_product(monkeypatch: pytest.MonkeyPatch) -> None:
    setup_settings(monkeypatch)
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/products/detail"):
            return httpx.Response(200, json=product(price="12.50", stock_by_location={"A": 2, "B": 3}))
        return httpx.Response(200, json=[product()])

    async with EktClient(TestMapper(), transport=httpx.MockTransport(handler)) as client:
        price = await client.check_price("A-1")
        stock = await client.check_stock("A-1")

    assert price.price == Decimal("12.50")
    assert isinstance(stock, EktStockCheck)
    assert stock.total_quantity == 5
    detail_requests = [request for request in requests if request.url.path.endswith("/products/detail")]
    assert all(request.url.params["id"] == "id-A-1" for request in detail_requests)


async def test_article_lookup_walks_pages_until_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    setup_settings(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params["page"]
        return httpx.Response(200, json=[product("other")] if page == "1" else [product("wanted")] if page == "2" else [])

    async with EktClient(TestMapper(), transport=httpx.MockTransport(handler)) as client:
        found = await client.get_product_by_article("WANTED")
    assert found.article == "wanted"


async def test_article_lookup_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    setup_settings(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    async with EktClient(TestMapper(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(EktProductNotFoundError):
            await client.get_product_by_article("missing")


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (400, EktClientRequestError),
        (401, EktAuthenticationError),
        (403, EktAuthenticationError),
        (404, EktNotFoundError),
        (422, EktClientRequestError),
        (500, EktServerError),
        (503, EktServerError),
    ],
)
async def test_http_status_errors_are_classified(
    monkeypatch: pytest.MonkeyPatch, status_code: int, error_type: type[Exception]
) -> None:
    setup_settings(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text="response body may contain sensitive data")

    async with EktClient(TestMapper(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(error_type):
            await client.get_products_page()


async def test_invalid_json_is_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    setup_settings(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"{broken", headers={"content-type": "application/json"})

    async with EktClient(TestMapper(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(EktInvalidJsonError):
            await client.get_products_page()


async def test_unexpected_external_shape_is_hidden_by_mapper_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    setup_settings(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unknown-envelope": []})

    async with EktClient(TestMapper(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(EktResponseFormatError):
            await client.get_products_page()


async def test_timeout_retries_only_controlled_read_attempts_and_credentials_are_not_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    setup_settings(monkeypatch, retries=1)
    count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        raise httpx.ReadTimeout("timeout", request=request)

    caplog.set_level(logging.WARNING)
    async with EktClient(TestMapper(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(EktTimeoutError):
            await client.get_products_page()

    assert count == 2
    assert "mock-user" not in caplog.text
    assert "mock-password" not in caplog.text


async def test_server_error_is_retried_once_then_returns_response(monkeypatch: pytest.MonkeyPatch) -> None:
    setup_settings(monkeypatch, retries=1)
    count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(503) if count == 1 else httpx.Response(200, json=[product()])

    async with EktClient(TestMapper(), transport=httpx.MockTransport(handler)) as client:
        products = await client.get_products_page()

    assert count == 2
    assert products[0].article == "A-1"


async def test_connection_error_is_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    setup_settings(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    async with EktClient(TestMapper(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(EktConnectionError):
            await client.get_products_page()


async def test_missing_price_or_stock_is_not_fabricated(monkeypatch: pytest.MonkeyPatch) -> None:
    setup_settings(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/products/detail"):
            return httpx.Response(200, json=product())
        return httpx.Response(200, json=[product()])

    async with EktClient(TestMapper(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(EktDataUnavailableError):
            await client.check_price("A-1")
        with pytest.raises(EktDataUnavailableError):
            await client.check_stock("A-1")


async def test_detail_must_match_the_article_found_in_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    setup_settings(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/products/detail"):
            return httpx.Response(200, json=product("wrong-article", price="1"))
        return httpx.Response(200, json=[product("A-1")])

    async with EktClient(TestMapper(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(EktResponseFormatError):
            await client.check_price("A-1")
