# Chat Service Backend

Базовый backend чат-сервиса на Python, FastAPI, Pydantic, PostgreSQL, SQLAlchemy и Alembic. В этой версии нет интеграций с ekt.kz, LLM и обработки файлов.

## Архитектура

- `app/api/routes` — HTTP endpoints.
- `app/schemas` — Pydantic-схемы запросов и ответов.
- `app/models` — SQLAlchemy-модели.
- `app/repositories` — доступ к данным.
- `app/services` — ошибки и прикладная логика.
- `app/integrations` — место для будущих внешних интеграций.
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

Compose defaults предназначены для локальной разработки. Для общего/боевого окружения задайте собственный пароль через некоммитящийся `.env` или секреты платформы.
