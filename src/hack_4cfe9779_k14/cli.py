"""Local terminal chat; a single process owns a single ephemeral conversation."""

import argparse
import sys

from pydantic import ValidationError

from .catalog import Catalog
from .consultant import MAX_HISTORY, MODEL, Consultant, ConsultantError, Reply, Turn


def show(reply: Reply, as_json: bool) -> None:
    if as_json:
        print(reply.model_dump_json(indent=2))
        return
    print(f"\nКонсультант: {reply.reply}")
    for product in reply.products:
        price = "не указана" if product.price is None else f"{product.price:g} {product.currency}"
        stock = "неизвестен" if product.stock is None else f"{product.stock:g} {product.unit}"
        print(f"  {product.sku} — {product.name}; цена: {price}; остаток: {stock}")
        for certificate in product.certificates:
            print(f"  {certificate.title}: {certificate.url}")
    if reply.sources:
        print("Источники:")
        for source in reply.sources:
            print(f"  [{source.id}] {source.title}" + (f" — {source.url}" if source.url else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description=f"ИИ-консультант EKT на {MODEL}; локальный прототип без бэкенда.")
    parser.add_argument("--message", help="Один вопрос вместо интерактивного диалога")
    parser.add_argument("--catalog", help="Путь к JSON-снимку; по умолчанию встроенный демокаталог")
    parser.add_argument("--json", action="store_true", help="Показать полный JSON для интеграции")
    parser.add_argument("--search", metavar="QUERY", help="Локальный поиск без модели, ключа и сети")
    args = parser.parse_args()
    if args.search is not None and args.message is not None:
        parser.error("Выберите --search или --message")
    try:
        catalog = Catalog.load(args.catalog)
    except (OSError, ValidationError, ValueError):
        parser.exit(2, "Не удалось загрузить каталог. Проверьте путь и схему в docs/consultant.md.\n")
    if args.search is not None:
        import json

        print(json.dumps({"mode": catalog.mode, "products": [p.model_dump(mode="json")
                         for p in catalog.search(args.search)]}, ensure_ascii=False, indent=2))
        return
    try:
        consultant = Consultant(catalog)
    except ConsultantError as error:
        parser.exit(2, f"{error}\n")
    try:
        if args.message is not None:
            show(consultant.answer(args.message), args.json)
            return
        print(f"EKT · {MODEL} · каталог: {catalog.mode}. /exit — выход, /reset — очистить историю.")
        print("Корзина и реальный сайт не подключены. История хранится только до выхода.")
        history: list[Turn] = []
        while True:
            try:
                message = input("\nВы: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if message == "/exit":
                break
            if message == "/reset":
                history.clear()
                print("История очищена.")
                continue
            if not message:
                continue
            try:
                reply = consultant.answer(message, history=history)
            except ConsultantError as error:
                print(f"Ошибка: {error}", file=sys.stderr)
                continue
            show(reply, args.json)
            context = reply.model_dump_json(include={"reply", "products"})
            # Retain exact IDs/SKUs for follow-up questions, without persistence on disk.
            history.extend([Turn(role="user", content=message), Turn(role="assistant", content=context[:16000])])
            history = history[-MAX_HISTORY:]
    except ConsultantError as error:
        parser.exit(2, f"{error}\n")
    except KeyboardInterrupt:
        print("\nЗапрос остановлен.", file=sys.stderr)
    finally:
        consultant.close()
