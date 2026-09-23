# Backend API

Исполняемый backend сохраняет существующую структуру проекта в [`../app`](../app): FastAPI routes, schemas, services, repositories и integrations уже разделены по слоям. Этот каталог обозначает границу API в корневой структуре проекта и хранит API-ориентированную документацию; перенос рабочего Python-пакета сюда не нужен и нарушил бы существующие импорты и миграции.

Контракт HTTP и формат ошибок описаны в [`../docs/api-conventions.md`](../docs/api-conventions.md).
Контракт для отдельно разрабатываемого browser-клиента: [`../docs/frontend-integration.md`](../docs/frontend-integration.md).
