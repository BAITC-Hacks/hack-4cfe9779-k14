# Каталог, adapter и поиск

`CatalogService` — единственная точка доступа dialogue layer к каталогу. Он получает данные через `CatalogAdapter`, поэтому локальный PostgreSQL-индекс, mock dataset и EKT transport не проникают в чат или маршруты.

## Adapter

`CatalogAdapter` поддерживает точный артикул, свежую карточку по partner id и постраничную выгрузку. Реализации:

- `MockCatalogAdapter` читает только [`testdata/mock_catalog.json`](../testdata/mock_catalog.json); это default для локального запуска;
- `EktCatalogAdapter` оборачивает существующий `EktClient` и использует лишь документированные GET-пути. В приложении подключён `LiveEktResponseMapper`, основанный на полученных ответах API;
- `UnavailableCatalogAdapter` возвращает безопасную нормализованную ошибку при отсутствии обязательной конфигурации EKT.

`python -m app.catalog_sync` или `POST /api/catalog/index/refresh` обновляет индекс страницами. Docker Compose выполняет синхронизацию после миграций. В режиме EKT при старте загружается `CATALOG_SYNC_PAGES` страниц (по умолчанию пять); просмотр следующих страниц расширяет индекс. Это частичный каталог.

## Модель и неизвестные значения

`products` хранит артикул, partner id, название, бренд, категорию, характеристики, кэшированные цену/остатки/доступность, сертификаты и `source_fields`. `source_field_presence` отдельно отмечает, был ли ключ в ответе источника: это отличает omission от `null`, `0`, `{}` и `[]`.

Кэшированные поля применяются только для поиска и отображения кандидатов. `GET /api/catalog/products/{article}/fresh` всегда вызывает adapter и возвращает его нормализованную карточку; `GET /api/catalog/products/{article}/current` не подставляет значения из индекса при ошибке источника.

## Поиск

1. Точный локальный `article` имеет приоритет.
2. SKU-подобный запрос проверяется строго по артикулу. В режиме EKT артикул должен присутствовать в загруженной части индекса; details читаются по его partner ID. Неизвестный SKU возвращает пустой результат, а не fuzzy-совпадение.
3. Обычный текст ищется PostgreSQL `plainto_tsquery('simple', ...)` по названию, артикулу, бренду, категории, описанию, характеристикам и `source_fields`.
4. `characteristics` применяются через JSONB containment. Пустой текст разрешён только вместе с этим фильтром.

Индексный backend находится за `CatalogRepository`; его можно заменить без изменения `CatalogService` или dialogue layer.

## Аналоги и замены

Подбор замен находится в отдельном `AnalogService` поверх `CatalogService`. Он сначала получает свежие карточки, применяет fail-closed правила `CompatibilityRules` по категории и обязательным техническим параметрам, затем ранжирует только допущенные позиции. Сходство названия не может обойти compatibility filter. Каждый результат содержит структурированное объяснение совпадений, различий и неизвестных полей. Текущие правила кабелей — только demo для mock dataset; подробности и необходимый production-контракт описаны в [analog-replacements.md](analog-replacements.md).

## API

- `POST /api/catalog/products` — upsert локальной нормализованной карточки.
- `POST /api/catalog/index/refresh` — контролируемая загрузка adapter в индекс.
- `GET /api/catalog/search?q=...&characteristics={...}&limit=20` — exact/text/spec search.
- `GET /api/catalog/products/{article}/fresh` — прямые свежие details adapter.
- `GET /api/catalog/products/{article}/current` — свежие цена/остатки/доступность без cache fallback.

- `GET /api/catalog/products?limit=100` — текущая индексная выдача.
- `GET /api/catalog/source-page?page=N` — страница источника с обновлением индекса.
- `GET /api/catalog/status` — режим каталога/корзины и наличие конфигурации модели, без секретов.
