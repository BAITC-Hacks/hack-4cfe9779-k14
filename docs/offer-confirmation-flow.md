# Безопасное подтверждение предложения корзины

`OfferService` реализует единственный серверный путь изменения корзины. LLM не импортирует этот сервис, не получает `CartGateway` и не может вызвать его через structured output.

## API

- `POST /api/chat/sessions/{session_id}/offers` создаёт предложение после проверки текущей карточки каталога. Тело: `product_identifier`, `article`, `quantity`. Chat intent может создать такой же `pending_offer` только через узкий server-owned `OfferProposalCreator`; ни LLM, ни browser не получают cart write capability.
- `POST /api/chat/sessions/{session_id}/offers/{offer_id}/confirm` подтверждает ровно один offer. Заголовок `Idempotency-Key` обязателен.

Произвольный текст вроде «да» не вызывает этот route и не меняет корзину. Подтверждение всегда требует path-параметр конкретного `offer_id`.

## PendingOffer

`pending_offers` содержит `id` (в API `offer_id`), `session_id`, `product_identifier`, `article`, `quantity`, `price_at_offer`, `created_at`, `expires_at`, `status`, служебный JSON payload и server-owned `cart_context`. Он привязывает предложение к `chat_session`; client не передаёт и не может заменить cart owner или cart id. Аутентифицированный пользователь пока не реализован, поэтому session — единственный доступный owner context. Состояния:

- `pending` — ожидает подтверждения;
- `confirmed` — запись в корзину подтверждена gateway;
- `expired` — срок истёк;
- `rejected` — товар, цена или остаток не подходят;
- `failed` — EKT или корзина не позволили безопасно завершить сценарий.

## Transaction flow подтверждения

1. Сервер открывает транзакцию PostgreSQL.
2. Он выбирает offer по `offer_id` и `session_id` через `SELECT … FOR UPDATE`. Два подтверждения одного offer не могут пройти этот участок одновременно.
3. В той же транзакции ищется запись `idempotency_keys` со scope `cart-confirm:{offer_id}` и ключом из заголовка. Если уже есть сохранённый результат, он возвращается без EKT и без корзины.
4. Если ключ новый, сервер резервирует его. Истекающий срок ключа задаёт `IDEMPOTENCY_KEY_TTL_SECONDS`.
5. Проверяется статус и `expires_at`. Неподтверждаемое предложение не записывается в корзину.
6. Пока offer заблокирован, сервер повторно вызывает EKT и проверяет совпадение product ID/артикула, текущую цену, полные остатки и доступность нужного количества.
7. Если цена изменилась, старый offer получает `rejected`, создаётся новый `pending` offer с новой ценой, а клиент получает `price_changed`. Новый `offer_id` нужно подтвердить отдельно.
8. При недостатке остатка product offer становится `rejected`. При ошибке EKT — `failed`. В обоих случаях cart gateway не вызывается и кэшированные данные не используются.
9. Только если цена и остаток совпали, сервер через `CartGateway.resolve_cart` получает корзину для той же session, затем вызывает `add_item`. Для gateway сервер строит стабильный operation key из `offer_id` и client `Idempotency-Key`, чтобы одинаковый ключ разных предложений не столкнулся в одной корзине. У gateway должна быть документированная идемпотентность: это защищает от сбоя процесса после внешней записи, но до PostgreSQL commit.
10. Сразу после write сервер выполняет `CartGateway.get_cart` и проверяет cart id и фактическую позицию/количество. HTTP-статус write сам по себе не делает offer подтверждённым.
11. Только при успешном read-back offer получает `confirmed`, snapshot корзины и подтверждённая ссылка возвращаются клиенту, а этот verified snapshot сохраняется вместе с результатом идемпотентности. Повтор confirmation с другим client key не пишет корзину повторно и может вернуть только этот сохранённый verified snapshot. Если read-back не совпал, offer имеет `failed`, а API не заявляет об успешном добавлении.

Вторая параллельная попытка с другим ключом дождётся row lock и увидит `confirmed`; cart gateway не вызовется повторно. Повтор с тем же ключом возвращает сохранённый результат.

## Ограничение интеграции EKT

Существующая документация не подтверждает endpoint корзины EKT. `UnavailableCartGateway` — default и намеренно возвращает безопасную ошибку, не симулируя запись. `MockCartGateway` доступен только при явном `CART_ADAPTER_MODE=mock`; он хранит demo-корзины в памяти процесса, строит `mock://` ссылку и не является интеграцией ekt.kz.

Production gateway следует реализовать только после получения partner contract: как определить владельца/корзину, add и update semantics, read-back состояния, подтверждённую ссылку, авторизацию, format результата, idempotency key и поведение при timeout после write. Нельзя угадывать эти endpoints или переносить mock URL в production.

## Очистка

Истёкшие offers и idempotency keys удаляются командой `python -m app.maintenance`. Она также удаляет истёкшие нормализованные данные вложений, обрабатывает не более `CLEANUP_BATCH_SIZE` записей каждого типа за запуск и подходит для запуска scheduler'ом платформы.
