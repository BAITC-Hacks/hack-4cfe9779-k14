"""Map the authenticated EKT list/detail responses observed on 2026-09-23.

No cart routes, inferred certificates or guessed unit/compatibility values.
"""
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

from app.integrations.ekt_client import EktProduct

CATEGORIES = {
    "kabel_provod": "Кабель / Провод",
    "svetilniki_lampy": "Светильники / Лампы",
    "nizkovoltnaya_apparatura": "Низковольтная аппаратура",
    "kabelenesushchie_sistemy": "Кабеленесущие системы",
    "izdeliya_dlya_montazha_i_instrument": "Изделия для монтажа и инструмент",
    "prochee_oborudovanie": "Прочее оборудование",
    "shkafy_shchity": "Шкафы / Щиты",
    "rozetki_vyklyuchateli_korobki": "Розетки/Выключатели/Коробки",
    "avtomatizatsiya": "Автоматизация",
    "spets_predlozhenie": "Спецпредложения EKT",
}


def amount(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        return None
    return result if result.is_finite() and result >= 0 else None


def safe_ekt_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    url = urlparse(value)
    if url.scheme == "https" and url.hostname and (url.hostname == "ekt.kz" or url.hostname.endswith(".ekt.kz")) and not url.username and not url.password:
        return value
    return None


class LiveEktResponseMapper:
    def parse_products_page(self, payload: Any) -> list[EktProduct]:
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise ValueError("Expected EKT items envelope")
        return [self.parse_product_detail(row) for row in payload["items"]]

    def parse_product_detail(self, payload: Any) -> EktProduct:
        if not isinstance(payload, dict):
            raise ValueError("Expected EKT product")
        identifier, article, name = payload.get("id"), payload.get("article"), payload.get("name")
        if isinstance(identifier, bool) or not isinstance(identifier, (int, str)) or not str(identifier).isdigit():
            raise ValueError("Invalid EKT identifier")
        if not isinstance(article, str) or not article.strip() or not isinstance(name, str) or not name.strip():
            raise ValueError("Missing EKT article/name")
        properties = payload.get("properties")
        if properties is not None and not isinstance(properties, dict):
            raise ValueError("Invalid properties")
        stores = payload.get("stores")
        stock = None
        if stores is not None:
            if not isinstance(stores, list):
                raise ValueError("Invalid stores")
            stock = {}
            for store in stores:
                if not isinstance(store, dict) or not isinstance(store.get("name"), str):
                    raise ValueError("Invalid store")
                quantity = amount(store.get("quantity"))
                # The backend cart currently supports whole units only. Preserve
                # fractional/malformed stock as unknown, never round it for sale.
                if quantity is None or quantity != quantity.to_integral_value():
                    stock = None
                    break
                key = f"{store['name']} [{store.get('id', '')}]"
                if key in stock:
                    raise ValueError("Duplicate store")
                stock[key] = int(quantity)
        url = safe_ekt_url(payload.get("url"))
        category = next((label for slug, label in CATEGORIES.items() if url and f"/catalog/{slug}/" in url), None)
        props = properties or {}
        # Keep technical fields verbatim. CML2/internal/recommendation fields are
        # retained as source metadata, not invented technical specifications.
        attributes = {key: value for key, value in props.items() if not key.startswith("CML2_") and key not in {"BRAND_PRIORITY", "NOVINKA", "SPETSPREDLOZHENIE", "RECOMMEND", "IMYAKARTINKI"}}
        return EktProduct(
            id=str(identifier), article=article.strip(), name=name.strip(),
            price=amount(payload.get("price")), stock_by_location=stock,
            description=payload.get("description") if isinstance(payload.get("description"), str) else None,
            attributes=attributes, category=category,
            brand=props.get("TORGOVAYA_MARKA") if isinstance(props.get("TORGOVAYA_MARKA"), str) else None,
            certificates=None,
            source_fields={"data_origin": "ekt/live", "url": url, "image": safe_ekt_url(payload.get("image")),
                           "quantity": payload.get("quantity"), "offers": payload.get("offers"), "properties": props},
            source_field_presence={"characteristics": "properties" in payload, "certificates": False,
                                   "cached_price": "price" in payload, "cached_stock_by_location": "stores" in payload},
        )
