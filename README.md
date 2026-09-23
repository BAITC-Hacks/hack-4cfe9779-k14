# Chat Service Backend

Базовый backend чат-сервиса на Python, FastAPI, Pydantic, PostgreSQL, SQLAlchemy и Alembic. Добавлен изолированный серверный адаптер `EktClient` на `httpx`; интеграции с LLM и обработка файлов не входят в проект.

## Архитектура

- `app/api/routes` — HTTP endpoints.
- `app/schemas` — Pydantic-схемы запросов и ответов.
- `app/models` — SQLAlchemy-модели.
- `app/repositories` — доступ к данным.
- `app/services` — ошибки и прикладная логика.
- `app/integrations` — внешние адаптеры; `ekt_client.py` изолирует HTTP API ekt.kz.
- `app/config` — настройки и подключение к PostgreSQL.
- `alembic` — миграции схемы.

Каталог хранит характеристики в PostgreSQL `JSONB`, имеет уникальный индексированный артикул и полнотекстовый `tsvector` с GIN-индексом. Триггер PostgreSQL обновляет поисковый вектор при изменении товара. Временные предложения и ключи идемпотентности имеют `created_at`, `expires_at` и индексы истечения срока для последующей очистки.

## Запуск локально

Скопируйте пример настроек и при необходимости измените значения:

```bash
cp .env.example .env
```

Запустите PostgreSQL локально, затем установите зависимости и примените миграции:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Swagger UI: <http://127.0.0.1:8000/docs>; проверка состояния: <http://127.0.0.1:8000/health>.

## Docker Compose

Одной командой запускаются API и PostgreSQL. Compose автоматически применяет миграции перед запуском API:

```bash
cp .env.example .env
docker compose up --build
```

Остановка контейнеров:

```bash
docker compose down
```

Чтобы также удалить данные PostgreSQL, используйте `docker compose down -v`.

## Миграции

```bash
alembic upgrade head
alembic revision --autogenerate -m "describe schema change"
alembic downgrade -1
```

Для миграций локально необходим доступный PostgreSQL. `DATABASE_URL` задаётся в `.env`; не коммитьте `.env` и реальные пароли.

## Тесты

```bash
pytest
```

Тесты health endpoint и моделей не требуют работающего PostgreSQL. Интеграционный health-check можно выполнить при запущенной базе через `curl http://localhost:8000/health`.

## Переменные окружения

| Переменная | Назначение | По умолчанию |
| --- | --- | --- |
| `APP_NAME` | Имя API | `Chat Service API` |
| `APP_ENV` | Окружение | `development` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |
| `DATABASE_URL` | SQLAlchemy DSN | Локальный PostgreSQL `chat` |
| `POSTGRES_DB` | Имя базы в Compose | `chat` |
| `POSTGRES_USER` | Пользователь в Compose | `chat` |
| `POSTGRES_PASSWORD` | Пароль в Compose | обязателен в `.env` |
| `API_PORT` | Порт API на хосте | `8000` |
| `EKT_API_BASE_URL` | Базовый URL API ekt.kz | `https://ekt.kz/api/` |
| `EKT_API_USERNAME` | Basic Auth логин, только сервер | не задан |
| `EKT_API_PASSWORD` | Basic Auth пароль, только сервер | не задан |

Compose defaults предназначены для локальной разработки. Для общего/боевого окружения задайте собственный пароль через некоммитящийся `.env` или секреты платформы.

## Интеграция ekt.kz

`EktClient` находится в `app/integrations/ekt_client.py`. Credentials `EKT_API_USERNAME` и `EKT_API_PASSWORD` читаются только сервером из environment/`.env`; Compose не отправляет Basic Auth в браузер. Известные GET-пути описаны в `docs/ekt-integration.md`. Формат JSON неизвестен, поэтому адаптер принимает `EktResponseMapper`, который должен быть реализован по документации партнёра. Корзина не подключена: endpoints корзины в материалах не найдены. Mock HTTP tests запускаются вместе с `pytest`.

Логи приложения выводятся как JSON. Ошибки EKT содержат только тип события, операцию, HTTP-статус и тип исключения; Basic Auth, тела запросов и ответов не логируются.

## Каталог и поиск

`CatalogService` использует локальный PostgreSQL-каталог и скрывает SQLAlchemy от API и будущего чата. Точный поиск по уникальному артикулу имеет приоритет. Если точного совпадения нет, применяется полнотекстовый PostgreSQL-поиск по названию, описанию, бренду и характеристикам JSONB. Фильтр `characteristics` работает через JSONB containment; отдельный Elasticsearch/OpenSearch не используется.

Локальные `cached_price`, `cached_stock_by_location` и `cached_available` не подтверждают актуальное состояние. Перед предложением вызывайте `CatalogService.get_current_availability(article)`: он получает текущую карточку через `EktClient`. При недоступности ekt.kz сервис возвращает `current=false` и не подставляет локальную цену или остаток. Полный контракт и тестовые endpoints: [docs/catalog.md](docs/catalog.md).

## Чат и LLM

API чата создаёт сессии, сохраняет user/assistant сообщения и выдаёт историю:

- `POST /api/chat/sessions`
- `POST /api/chat/sessions/{session_id}/messages`
- `GET /api/chat/sessions/{session_id}/messages`

`ChatService` зависит от абстрактного `LLMClient`, а текущая реализация использует настраиваемый OpenAI-compatible HTTP endpoint без SDK. Модель выдаёт валидируемый Pydantic structured output, но не получает доступ к PostgreSQL, ekt.kz или корзине. Корзина не изменяется ни при каком ответе LLM. Лимит истории и необходимые environment variables приведены в [docs/chat-flow.md](docs/chat-flow.md).
