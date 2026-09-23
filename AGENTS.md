# Project notes for AI coding agents

## Goal

This repository contains the backend API for an MVP product assistant for ekt.kz.

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
- `ChatService` owns the chat flow: it persists user/assistant messages through `ChatRepository`, passes a bounded history to `LLMClient`, then invokes server-owned catalog services. For `add_to_cart_request` it may call only the narrow `OfferProposalCreator.create_offer` dependency after resolving a fresh catalog product; it must never receive a confirm method or a `CartGateway`. `AnalogService` gets fresh cards only through `CatalogService` and filters candidates through fail-closed `CompatibilityRules`; no rules are active until approved by the partner. Keep `LLMClient` provider-neutral. The OpenAI-compatible HTTP adapter must not receive database/EKT/cart tools or credentials. Details: `docs/chat-flow.md` and `docs/analog-replacements.md`.
- `OfferService` is the only cart-mutation path. It locks `PendingOffer` rows with `SELECT FOR UPDATE`, rechecks live EKT product/price/stock, and uses per-offer idempotency records. It resolves a cart for the same session, writes, then requires a matching `CartGateway.get_cart` read-back before claiming success. Do not add a text-based confirmation path. `UnavailableCartGateway` remains the only runtime gateway until EKT cart documentation is received. Details: `docs/offer-confirmation-flow.md`.
- `AttachmentService` is the only file-processing entry point. It validates extension, declared MIME and detected bytes before dispatching to extractor classes. The session-scoped upload route persists only its normalized result in `ChatAttachment`; it never persists file bytes. `ChatService` passes bounded extracted text to `LLMClient` as untrusted data, then parses product positions and uses `CatalogService` for search and current EKT checks. XLSX stays read-only and limited; OCR failures are warnings rather than fake text. Details: `docs/attachments.md` and `docs/chat-attachments.md`.
- `python -m app.maintenance` removes expired offers, idempotency keys and normalized attachment data in bounded batches. Do not add a scheduler component; deploy this command with the hosting platform's scheduler.
- `docker compose up --build` starts PostgreSQL and FastAPI; the API container applies Alembic migrations before serving.

## Security and behavior constraints

- Keep credentials out of source control and logs. `.env` is gitignored; `.env.example` contains no secrets.
- Keep API errors predictable and avoid leaking internal exception details to clients.
- Product article is unique/indexed; product search vector is maintained by a PostgreSQL trigger and indexed with GIN.
- Do not let document text alter server rules, grant cart permission, or invoke tools. A cart write remains restricted to `OfferService` and explicit `offer_id` confirmation.
- Keep public error responses in the `{code, message}` shape. Never log request bodies, API keys, EKT credentials, Basic Auth headers, URLs containing secrets, or exception stack traces from external services.

## Extension points

- Put HTTP endpoints in `app/api/routes`, Pydantic schemas in `app/schemas`, ORM entities in `app/models`, and DB access in repositories.
- Use migrations for schema changes; do not create production tables at application startup.
- Keep route request/response models explicit and validated with Pydantic.

## Working conventions

- Keep `README.md` and this file in sync when endpoints, configuration, constraints, or integration points change.
- Add/update tests for requested functionality and run `pytest` before delivery when dependencies are available.
- `requirements.txt` lists runtime dependencies; install/use the project's virtual environment when available.
