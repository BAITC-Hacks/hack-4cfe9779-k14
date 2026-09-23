# Каталог, adapter и поиск

`CatalogService` — единственная точка доступа dialogue layer к каталогу. Он получает данные через `CatalogAdapter`, поэтому локальный PostgreSQL-индекс и будущий EKT transport не проникают в чат или маршруты.

## Adapter

`CatalogAdapter` поддерживает точный артикул, свежую карточку по partner id и постраничную выгрузку. Реализации:

- `EktCatalogAdapter` оборачивает существующий `EktClient` и использует лишь документированные GET-пути. Его можно создать только с подтверждённым `EktResponseMapper`;
- `UnavailableCatalogAdapter` — единственная runtime-реализация до появления mapper и возвращает безопасную нормализованную ошибку.

`python -m app.catalog_sync` или `POST /api/catalog/index/refresh` обновляет индекс страницами только после подключения утверждённого adapter. Docker Compose не синхронизирует каталог без такого adapter.

## Модель и неизвестные значения

`products` хранит артикул, partner id, название, бренд, категорию, характеристики, кэшированные цену/остатки/доступность, сертификаты и `source_fields`. `source_field_presence` отдельно отмечает, был ли ключ в ответе источника: это отличает omission от `null`, `0`, `{}` и `[]`.

Кэшированные поля применяются только для поиска и отображения кандидатов. `GET /api/catalog/products/{article}/fresh` всегда вызывает adapter и возвращает его нормализованную карточку; `GET /api/catalog/products/{article}/current` не подставляет значения из индекса при ошибке источника.

## Поиск

1. Точный локальный `article` имеет приоритет.
2. SKU-подобный запрос, которого нет в индексе, проверяется adapter'ом строго по артикулу. Неизвестный SKU возвращает пустой результат, а не fuzzy-совпадение.
3. Обычный текст ищется PostgreSQL `plainto_tsquery('simple', ...)` по названию, артикулу, бренду, категории, описанию, характеристикам и `source_fields`.
4. `characteristics` применяются через JSONB containment. Пустой текст разрешён только вместе с этим фильтром.

Индексный backend находится за `CatalogRepository`; его можно заменить без изменения `CatalogService` или dialogue layer.

## Аналоги и замены

Подбор замен находится в отдельном `AnalogService` поверх `CatalogService`. Он сначала получает свежие карточки, применяет fail-closed правила `CompatibilityRules` по категории и обязательным техническим параметрам, затем ранжирует только допущенные позиции. Сходство названия не может обойти compatibility filter. Каждый результат содержит структурированное объяснение совпадений, различий и неизвестных полей. Пока партнёр не утвердил профиль категории, `UnavailableCompatibilityRules` не предлагает замены. Подробности и необходимый production-контракт описаны в [analog-replacements.md](analog-replacements.md).

## API

- `POST /api/catalog/products` — upsert локальной нормализованной карточки.
- `POST /api/catalog/index/refresh` — контролируемая загрузка adapter в индекс.
- `GET /api/catalog/search?q=...&characteristics={...}&limit=20` — exact/text/spec search.
- `GET /api/catalog/products/{article}/fresh` — прямые свежие details adapter.
- `GET /api/catalog/products/{article}/current` — свежие цена/остатки/доступность без cache fallback.
