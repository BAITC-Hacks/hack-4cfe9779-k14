import re
from uuid import UUID

from app.schemas.attachment_parsing import ParsedAttachmentItem
from app.schemas.attachments import AttachmentResult


class AttachmentItemParser:
    """Conservative parser for article/name/quantity data extracted from files."""

    _ARTICLE_HEADERS = {"article", "артикул", "sku", "код", "code"}
    _NAME_HEADERS = {"name", "product", "товар", "наименование", "название"}
    _QUANTITY_HEADERS = {"quantity", "qty", "count", "количество", "кол-во", "кол во"}
    _ARTICLE_PATTERN = re.compile(r"(?:артикул|article|sku|код)\s*[:#]?\s*([A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9._/-]{1,127})", re.I)
    _QUANTITY_PATTERN = re.compile(r"(?:количество|кол-во|qty|quantity)\s*[:#]?\s*(\d+)", re.I)
    _LINE_ITEM_PATTERN = re.compile(r"^\s*([A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9._/-]{1,127})\s+(?:x\s*)?(\d+)\s*$", re.I)

    def parse(self, attachment_id: UUID, result: AttachmentResult) -> list[ParsedAttachmentItem]:
        items = self._parse_tables(attachment_id, result)
        if items:
            return items
        return self._parse_text(attachment_id, result.text)

    def _parse_tables(self, attachment_id: UUID, result: AttachmentResult) -> list[ParsedAttachmentItem]:
        items: list[ParsedAttachmentItem] = []
        for table in result.tables:
            if not table.rows:
                continue
            header = [self._normalize_header(value) for value in table.rows[0]]
            article_index = self._header_index(header, self._ARTICLE_HEADERS)
            name_index = self._header_index(header, self._NAME_HEADERS)
            quantity_index = self._header_index(header, self._QUANTITY_HEADERS)
            if article_index is None and name_index is None:
                continue
            for row in table.rows[1:]:
                article = self._value(row, article_index)
                name = self._value(row, name_index)
                quantity = self._quantity(self._value(row, quantity_index))
                warnings = self._item_warnings(article, name, quantity, quantity_index is not None)
                if article or name:
                    items.append(ParsedAttachmentItem(
                        attachment_id=attachment_id, article=article, product_name=name,
                        quantity=quantity, warnings=warnings,
                    ))
        return items

    def _parse_text(self, attachment_id: UUID, text: str) -> list[ParsedAttachmentItem]:
        items: list[ParsedAttachmentItem] = []
        for line in text.splitlines():
            article_match = self._ARTICLE_PATTERN.search(line)
            simple_match = self._LINE_ITEM_PATTERN.match(line) if article_match is None else None
            if article_match is None and simple_match is None:
                continue
            article = article_match.group(1) if article_match else simple_match.group(1)
            quantity_match = self._QUANTITY_PATTERN.search(line)
            quantity = int(quantity_match.group(1)) if quantity_match else int(simple_match.group(2)) if simple_match else None
            warnings = ["quantity_ambiguous"] if quantity is None else []
            items.append(ParsedAttachmentItem(
                attachment_id=attachment_id, article=article, quantity=quantity, warnings=warnings,
            ))
        return items

    @staticmethod
    def _normalize_header(value: object) -> str:
        return str(value or "").strip().casefold()

    @staticmethod
    def _header_index(headers: list[str], variants: set[str]) -> int | None:
        return next((index for index, value in enumerate(headers) if value in variants), None)

    @staticmethod
    def _value(row: list[object], index: int | None) -> str | None:
        if index is None or index >= len(row) or row[index] is None:
            return None
        value = str(row[index]).strip()
        return value or None

    @staticmethod
    def _quantity(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            quantity = int(value)
        except ValueError:
            return None
        return quantity if quantity > 0 else None

    @staticmethod
    def _item_warnings(article: str | None, name: str | None, quantity: int | None, quantity_column_exists: bool) -> list[str]:
        warnings: list[str] = []
        if not article and not name:
            warnings.append("item_unrecognized")
        if quantity is None:
            warnings.append("quantity_ambiguous" if quantity_column_exists else "quantity_missing")
        return warnings
