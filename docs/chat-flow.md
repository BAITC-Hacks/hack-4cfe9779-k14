# API чата и LLM-интеграция

## Endpoints

- `POST /api/chat/sessions` создаёт сессию и возвращает `id`.
- `POST /api/chat/sessions/{session_id}/messages` принимает `{ "content": "..." }`, сохраняет сообщение, анализирует запрос и сохраняет ответ assistant.
- `GET /api/chat/sessions/{session_id}/messages` возвращает полную историю сессии.

Все тела запросов проверяются Pydantic. Пустые сообщения, лишние поля и сообщения длиннее 4000 символов отклоняются до бизнес-логики.

## Flow одного сообщения

1. Route передаёт сообщение в `ChatService`.
2. Сервис проверяет существование сессии и сохраняет пользовательское сообщение в PostgreSQL.
3. Сервис получает ограниченную историю только этой сессии и извлекает последний выбранный артикул из metadata assistant-сообщения. История другой сессии не читается.
4. `DeterministicDialogueRouter` сначала распознаёт SKU, сертификаты, наличие, характеристики, цены и условия покупки. Follow-up вроде «а сертификат у него есть?» получает артикул только из той же сессии.
5. Если deterministic route не сработал, `LLMClient` отправляет модели только system prompt и bounded history. У модели нет инструментов, SQL, доступа к EKT или корзине; она лишь возвращает валидируемую классификацию `ChatAnalysis`.
6. `ChatService` вызывает `CatalogService` для поиска и фактов. Точный артикул и полнотекстовый поиск выполняются сервером, а не моделью. Несколько кандидатов дают clarification вместо автоматического выбора.
7. Для наличия и цены сервер вызывает `get_current_availability`; для характеристик и сертификатов — `get_fresh_product`. Кэш каталога не выдаётся как свежий факт.
8. Для условий покупки сервис читает `PurchaseConditionsProvider`, а не prompt LLM. Demo-provider явно сообщает, что реальные условия ekt.kz не предоставлены.
9. Сервис формирует grounded ответ, сохраняет выбранный контекст в metadata assistant-сообщения и возвращает его клиенту.

`add_to_cart_request` — только классификация намерения. Чат отвечает, что товар не добавлен. Ни `LLMClient`, ни `ChatService` не вызывают API корзины; отдельная серверная логика предложения и явного подтверждения потребуется позже.

## LLM abstraction

`LLMClient` — protocol, используемый `ChatService`. Конкретный `OpenAICompatibleLLMClient` лежит в `app/integrations/llm_client.py` и использует `httpx`, без SDK. Он изолирует OpenAI-compatible contract: `messages`, `response_format=json_schema` и извлечение `choices[0].message.content`.

При timeout, сетевой/HTTP ошибке или невалидном JSON/schema сервис сохраняет безопасный ответ с intent `unknown`; некорректные данные модели не используются для поиска, EKT или мутации корзины. Deterministic intents продолжают работать, когда LLM не настроен.

## Environment variables

- `LLM_API_URL` — полный URL OpenAI-compatible chat-completions endpoint.
- `LLM_API_KEY` — API key, только в environment или некоммитящемся `.env`.
- `LLM_MODEL` — имя модели.
- `LLM_TEMPERATURE` — температура, по умолчанию `0`.
- `LLM_TIMEOUT_SECONDS` — полный timeout, по умолчанию `15`.
- `LLM_HISTORY_MESSAGE_LIMIT` — максимум последних сообщений для модели, по умолчанию `12`.

Логи сообщают только тип ошибки LLM. API key, сообщения, request body и response body не логируются.
