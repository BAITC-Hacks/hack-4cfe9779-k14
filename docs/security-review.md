# Security review

Проверка проведена перед первым развёртыванием. Автоматические тесты покрывают ключевые отказные пути; реальные EKT и cart credentials в тестах не используются.

| Область | Состояние | Мера |
| --- | --- | --- |
| Секреты, API keys | Готово | `.env` игнорируется; `.env.example` содержит только демонстрационные значения; `SecretStr` не сериализуется в ответы. |
| Basic Auth EKT | Готово | `httpx.BasicAuth` существует только в серверном `EktClient`; redirects отключены; headers, URL и тела не логируются. |
| SQL injection | Готово | SQLAlchemy expression API и bound parameters; полнотекстовый запрос строится `plainto_tsquery`. |
| Загрузка файлов | Готово | Лимит bytes, allowlist расширений, MIME и сигнатуры/OOXML-проверка; имя очищается через `Path.name`; XLSX read-only и лимитирован. |
| Path traversal | Готово | Бинарные файлы не сохраняются; извлекатели получают bytes, а имя файла нормализуется. |
| Prompt injection | Готово | В LLM попадает только ограниченное извлечение в `untrusted_attachment`; системный prompt запрещает выполнять инструкции вложения. |
| Размер запросов | Готово | Pydantic ограничивает сообщение, query и число attachment refs; upload stream ограничен `ATTACHMENT_MAX_BYTES`; текст для LLM — `ATTACHMENT_LLM_MAX_CHARS`. |
| Ошибки и логи | Готово | Публичные ошибки имеют `{code, message}`; неожиданные исключения скрыты; логируются тип и событие без request body, credentials или stack trace. |
| Корзина | Готово для безопасного отказа | `PendingOffer`, lock и idempotency защищают сценарий. Реальная запись невозможна без документированного cart contract EKT. |

Перед production требуется заменить development session model на аутентифицированную интеграцию сайта, ограничить CORS на фактический frontend origin и передавать секреты через secrets manager платформы.
