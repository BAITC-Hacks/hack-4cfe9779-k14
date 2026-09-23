# Локальный каталог и поиск

Локальный PostgreSQL-каталог служит для быстрого выбора кандидатов. Он не является источником подтверждённых цены, остатка или доступности для предложения пользователю.

## Модель и индексы

`products` содержит обычные колонки `article`, `external_id`, `name`, `description`, `brand` и кэшированные поля `cached_price`, `cached_stock_by_location`, `cached_available`. Разнородные технические параметры находятся в `characteristics JSONB`.

В миграции `20260923_0002_catalog_fields` добавлены бренд и партнёрский идентификатор. Кэшированные поля названы намеренно: они пригодны для синхронизации и отображения кандидата, но не подтверждают состояние товара.

Индексы PostgreSQL:

- уникальный B-tree по `article` для отдельного точного поиска;
- уникальный B-tree по `external_id`, когда он получен от партнёра;
- GIN по `search_vector` для полнотекстового поиска;
- GIN `jsonb_path_ops` по `characteristics` для containment-фильтров JSONB;
- B-tree по `brand`.

Триггер `products_search_vector_update` обновляет `search_vector` при вставке и изменении. Вектор содержит артикул, название и бренд с весом A, описание с весом B и JSONB-характеристики с весом C. Конфигурация `simple` избегает зависимости от одного словаря языка.

## Алгоритм поиска

`CatalogService.search_candidates` выполняет шаги:

1. Нормализует поисковую строку.
2. При непустой строке ищет точное равенство `article`. Если товар найден и удовлетворяет характеристикам, возвращает только его с `match_type=exact_article`.
3. Иначе выполняет PostgreSQL `plainto_tsquery('simple', query)` по `search_vector`, сортируя кандидаты через `ts_rank_cd`.
4. Если передан JSON-объект характеристик, применяет JSONB containment `characteristics @> filter`.

Пустой текст допускается только вместе с фильтром характеристик; тогда кандидаты выбираются по JSONB и сортируются по названию.

## API для проверки

- `POST /api/catalog/products` — сохранение или обновление товара по артикулу.
- `GET /api/catalog/search?q=...&characteristics={...}&limit=20` — кандидаты. `characteristics` должен быть JSON-объектом в query parameter.
- `GET /api/catalog/products/{article}/current` — результат проверки текущих данных. В базовой HTTP-конфигурации EKT-клиент ещё не связывается автоматически, поэтому ответ помечается `current=false`; чат должен получать `CatalogService` с настроенным `EktClient` и реальным `EktResponseMapper`.

## Проверка перед предложением

Перед созданием предложения вызовите `CatalogService.get_current_availability(article)`. Сервис всегда вызывает `EktClient.get_current_product_by_article`, затем берёт из ответа EKT цену, остатки и вычисляет доступность по сумме остатков. При timeout, сетевой ошибке или другой ошибке EKT он возвращает:

```json
{
  "current": false,
  "price": null,
  "stock_by_location": null,
  "available": null,
  "reason": "ekt_unavailable"
}
```

Кэшированные значения PostgreSQL в этом пути не используются. До получения реальной документации EKT также нельзя подключать преобразователь JSON или считать, что картовые endpoints существуют.
