# HTTP-конвенции API

Machine-readable contract доступен по `GET /openapi.json`; интерактивная версия — по `GET /docs`. Frontend должен опираться на стабильные `operationId` из OpenAPI, а не на внутренние имена Python-функций. Полный browser handoff: [frontend-integration.md](frontend-integration.md).

Успешные ответы — типизированные JSON-объекты, определённые Pydantic response models конкретного endpoint. Например, создание сессии возвращает `{ "id", "created_at" }`, а отправка сообщения — `ChatReply` с сообщениями пользователя и assistant.

Любая ожидаемая ошибка, включая ошибки валидации, имеет одну форму:

```json
{ "code": "validation_error", "message": "Request validation failed" }
```

`code` предназначен для обработки клиентом, `message` — безопасный текст для отображения. Внешние детали, request bodies, секреты и stack traces не возвращаются.
