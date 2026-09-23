# Project notes for AI coding agents

## Goal

This repository contains a generic backend skeleton for a chat service. Do not implement ekt.kz, LLM, or file-processing integrations unless the user asks.

## Current implementation

- Runtime: Python, FastAPI, Pydantic v2, async SQLAlchemy 2, PostgreSQL, Alembic. Entry point: `app/main.py` (`app.main:app`).
- Layers are separated under `app/api/routes`, `schemas`, `models`, `repositories`, `services`, `integrations`, and `config`.
- `GET /health` checks database connectivity and returns 503 if the database is unavailable.
- SQLAlchemy models and the initial Alembic migration cover chat sessions, messages, products with JSONB characteristics/full-text search, pending offers, and idempotency keys.
- Pending offers and idempotency keys have `created_at` and `expires_at` plus expiry indexes. A scheduled cleanup worker is intentionally not included yet.
- `.env.example` documents local settings. Real `.env` credentials must stay untracked.
- `app/integrations/ekt_client.py` is an explicitly requested server-side `httpx` Basic Auth adapter. Use only the documented paths in `docs/ekt-integration.md`; never guess the upstream JSON schema, and keep its mapping in `EktResponseMapper`. Partner credentials come from environment-backed settings only. No cart endpoints are confirmed, so do not invent them.
- `app/config/logging.py` configures JSON logs. EKT error logs must preserve event fields while excluding credentials, headers, URLs, and bodies.
- `CatalogService` is the only catalog entry point for routes/chat. `CatalogRepository` owns SQLAlchemy queries. Article lookup precedes PostgreSQL full-text search; JSONB characteristic filters use containment. Local product fields beginning with `cached_` must never be reported as current price/stock/availability: call `CatalogService.get_current_availability`, which asks EKT and returns `current=false` on an upstream failure.
- `ChatService` owns the chat flow: it persists user/assistant messages through `ChatRepository`, passes a bounded history to `LLMClient`, then invokes only server-owned `CatalogService` methods. Keep `LLMClient` provider-neutral. The OpenAI-compatible HTTP adapter must not receive database/EKT/cart tools or credentials. `add_to_cart_request` is classification only and must never mutate a cart. Details: `docs/chat-flow.md`.
- `OfferService` is the only cart-mutation path. It locks `PendingOffer` rows with `SELECT FOR UPDATE`, rechecks live EKT product/price/stock, and uses per-offer idempotency records. Do not add a text-based confirmation path. `CartGateway` is intentionally unavailable pending EKT cart documentation; never claim an add succeeded if that gateway is unavailable. Details: `docs/offer-confirmation-flow.md`.
- `docker compose up --build` starts PostgreSQL and FastAPI; the API container applies Alembic migrations before serving.

## Security and behavior constraints

- Keep credentials out of source control and logs. `.env` is gitignored; `.env.example` contains no secrets.
- Keep API errors predictable and avoid leaking internal exception details to clients.
- Product article is unique/indexed; product search vector is maintained by a PostgreSQL trigger and indexed with GIN.
- Do not add external integrations or file upload flows unless requested.

## Extension points

- Put HTTP endpoints in `app/api/routes`, Pydantic schemas in `app/schemas`, ORM entities in `app/models`, and DB access in repositories.
- Use migrations for schema changes; do not create production tables at application startup.
- Keep route request/response models explicit and validated with Pydantic.

## Working conventions

- Keep `README.md` and this file in sync when endpoints, configuration, constraints, or integration points change.
- Add/update tests for requested functionality and run `pytest` before delivery when dependencies are available.
- `requirements.txt` lists runtime dependencies; install/use the project's virtual environment when available.
