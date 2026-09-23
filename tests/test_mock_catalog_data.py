import json
from pathlib import Path

from app.schemas.catalog import CatalogProductUpsert


def test_mock_catalog_is_explicitly_synthetic_and_representative() -> None:
    path = Path(__file__).parents[1] / "testdata" / "mock_catalog.json"
    dataset = json.loads(path.read_text(encoding="utf-8"))

    assert dataset["dataset"] == "mock/demo data"
    products = [CatalogProductUpsert.model_validate(product) for product in dataset["products"]]
    assert any(product.cached_available is True for product in products)
    assert any(product.cached_stock_by_location == {"Алматы": 0} for product in products)
    assert any(product.certificates for product in products)
    assert any(product.certificates == [] for product in products)
    assert any(product.certificates is None for product in products)
    assert any(product.cached_stock_by_location and len(product.cached_stock_by_location) > 1 for product in products)
    assert dataset["unknown_sku_examples"] == ["DEMO-UNKNOWN-404"]
