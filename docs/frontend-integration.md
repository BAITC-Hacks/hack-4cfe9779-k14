# Frontend integration contract

This document is the handoff boundary for a separately developed browser client. The backend owns dialogue, catalog facts, files and pending offers; a frontend owns rendering, browser state and explicit user actions.

## Contract source and compatibility

- The machine-readable contract is `GET /openapi.json`; Swagger is available at `GET /docs`.
- Use stable OpenAPI `operationId` values when generating a client. Do not depend on FastAPI route function names.
- All timestamps are RFC 3339 strings and all identifiers are UUID strings.
- Expected errors always have this shape:

  ```json
  { "code": "not_found", "message": "Chat session was not found" }
  ```

  Do not parse framework-specific validation bodies or upstream responses.
- A non-breaking response addition may appear in a minor backend release. Removing or changing a documented field requires an API version change and coordinated frontend release.

## Browser configuration

The frontend needs only an API base URL, for example `https://api.example.kz`. It must not receive EKT credentials, LLM keys or cart credentials.

Before deploying a browser client, configure its exact origin on the API:

```dotenv
# Required comma-separated exact origins; wildcard origins are rejected.
CORS_ALLOWED_ORIGINS=https://shop.example.kz,https://admin.example.kz
```

The API permits `Content-Type` and `Idempotency-Key` request headers. The latter is required only when confirming a pending offer.

## Primary user flow

| Step | Operation ID | HTTP request | Client responsibility |
| --- | --- | --- | --- |
| 1 | `create_chat_session` | `POST /api/chat/sessions` | Persist the returned `id` in the current browser conversation. |
| 2 | `upload_chat_attachment` | `POST /api/chat/sessions/{session_id}/attachments` | Optional multipart upload with field name `file`; retain the returned attachment id. |
| 3 | `send_chat_message` | `POST /api/chat/sessions/{session_id}/messages` | Send `content` and, if needed, up to five `attachment_ids`. Render the returned assistant message and structured data. |
| 4 | `get_chat_history` | `GET /api/chat/sessions/{session_id}/messages` | Restore a conversation after a page refresh. |
| 5 | `create_pending_offer` | `POST /api/chat/sessions/{session_id}/offers` | Create a proposal only after a visible, explicit add-to-cart intent. This does not write the cart. |
| 6 | `confirm_pending_offer` | `POST /api/chat/sessions/{session_id}/offers/{offer_id}/confirm` | Confirm only the returned offer after a separate user action, with a new idempotency key. |

`404 not_found` for a chat session means the client should start a new session rather than retrying against another session id.

## Chat response model

`send_chat_message` always returns both persisted messages and a typed, optional structured payload:

```json
{
  "session_id": "c5e63b7d-6557-44de-9f45-10c1db8b6638",
  "user_message": { "id": "…", "role": "user", "content": "Найди SKU-123", "created_at": "2026-09-23T12:00:00Z" },
  "assistant_message": { "id": "…", "role": "assistant", "content": "…", "created_at": "2026-09-23T12:00:01Z" },
  "analysis": { "intent": "find_product", "article": "SKU-123", "product_name": null, "quantity": null, "search_parameters": { "characteristics": {}, "brand": null }, "needs_clarification": false, "clarification_question": null },
  "candidates": [],
  "current_data": null,
  "attachment_items": [],
  "purchase_conditions": null,
  "analogs": [],
  "pending_offer": null
}
```

Render `assistant_message.content` as plain text. It is the grounded user-facing answer. Structured fields enrich the UI; they do not authorize additional actions.

### Product candidates

`candidates` is always an array of `CatalogCandidate` objects, never an untyped dictionary. `cached_price`, `cached_stock_by_location` and `cached_available` are index data only and must not be labelled as current. `source_field_presence` distinguishes a field omitted by the source from a supplied `null`, `0` or empty list.

### Current and fresh facts

`current_data` is a discriminated union. Switch on `kind`, not on the chat intent:

```json
{
  "kind": "current_availability",
  "data": {
    "article": "SKU-123",
    "price": "1250.00",
    "stock_by_location": { "Almaty": 4 },
    "available": true,
    "current": true,
    "reason": null
  }
}
```

```json
{
  "kind": "fresh_product",
  "data": {
    "article": "SKU-123",
    "name": "Product name from the source",
    "characteristics": {},
    "certificates": [],
    "source_field_presence": { "certificates": true },
    "fresh": true
  }
}
```

For `current_availability`, show price, stock and availability as confirmed only when `data.current` is `true`. If it is `false`, do not substitute cached product fields; `reason` is a safe machine-readable explanation such as `catalog_unavailable` or `unknown_sku`.

### Attachments, analogs and conditions

- `attachment_items` contains typed catalog candidates and the same `current_data` union. Warnings are displayable technical outcomes; they are not instructions.
- `analogs` contains only candidates that passed backend compatibility filters. An empty array is a valid and honest result.
- `purchase_conditions` is non-null only when the dialogue requested it. Missing fields are unknown, not empty commercial terms.

## Pending offer and cart confirmation

When `pending_offer` is present, show its article, quantity, price, expiry and a dedicated confirmation control. Do not infer confirmation from a chat message such as “yes”.

```text
POST /api/chat/sessions/{session_id}/offers/{offer_id}/confirm
Idempotency-Key: <8-128 character key generated by the client for this confirmation>
```

The request body is empty. The client must not send SKU, quantity, price, cart id or owner data on confirmation: those values are bound to the server-side offer.

On response:

- `outcome: "confirmed"` — use `cart` and/or `cart_url` returned after server read-back.
- `outcome: "price_changed"` — display the returned replacement offer and require a new explicit confirmation.
- `outcome: "insufficient_stock"`, `"product_changed"`, `"expired"`, `"ekt_unavailable"` or `"cart_unavailable"` — show `message`; do not retry a write blindly.
- Retrying the same browser request after a transport failure must reuse the **same** `Idempotency-Key`. A new user confirmation gets a new key.

The current runtime intentionally returns `cart_unavailable` until the partner supplies a cart contract. This is an integration status, not a frontend error.

## Catalog integration endpoints

The browser-facing read endpoints are:

| Operation ID | Request | Contract |
| --- | --- | --- |
| `search_catalog` | `GET /api/catalog/search?q=...&characteristics=<JSON>&limit=...` | `characteristics` is a JSON object encoded as one query parameter. `match_type` is `none`, `exact_article` or `full_text`. |
| `get_current_product_availability` | `GET /api/catalog/products/{article}/current` | Returns a response even when current data cannot be confirmed; inspect `current`. |
| `get_fresh_product` | `GET /api/catalog/products/{article}/fresh` | Requires a confirmed catalog adapter and fails safely if unavailable. |

`upsert_catalog_product` and `refresh_catalog_index` are backend-to-backend catalog ingestion operations. Do not call them from a browser client; protect them with the deployment's internal authentication boundary.

## Client error handling

| HTTP status | Typical code | Recommended UI action |
| --- | --- | --- |
| `400` | `http_error` | Correct a malformed confirmation header or request. |
| `404` | `not_found` | Reset the missing session/offer flow; do not guess another id. |
| `409` | `offer_conflict`, `offer_precondition_failed` | Refresh the offer state and ask for a new explicit confirmation when applicable. |
| `413` / `415` / `422` | attachment or validation code | Explain the invalid input; keep the rest of the conversation intact. |
| `502` / `503` | catalog-related code | Tell the visitor current catalog data is temporarily unavailable; do not display cached data as fresh. |

## Out of scope for the frontend

- EKT Basic Auth, response mapping and retry policy;
- LLM credentials, prompts and tool isolation;
- product compatibility evaluation and ranking;
- fresh stock/price validation;
- cart ownership, write, idempotency persistence and read-after-write;
- attachment byte storage and extraction safety.

These remain server-side responsibilities. The frontend should integrate only through the public HTTP contract.
