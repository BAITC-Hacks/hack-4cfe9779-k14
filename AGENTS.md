# Project notes for AI coding agents

## Goal

This repository contains the backend API for an MVP product assistant for ekt.kz. The API should help a visitor find products, answer from verified catalog data, accept product documents/images, and support a safe, explicit cart-confirmation flow.

## Current implementation

- Runtime: Python, FastAPI, Pydantic. Entry point: `app/main.py` (`app.main:app`).
- `GET /health` is a liveness endpoint.
- `POST /api/chat/attachments` accepts PDF, DOC/DOCX, XLS/XLSX, and JPEG uploads up to 10 MiB. Files are written under the OS temporary directory with owner-only permissions. Metadata is associated with the authenticated development session in memory.
- `POST /api/chat/messages` accepts text and up to five uploaded attachment IDs. Attachment IDs must belong to the current session. The handler delegates to `ChatProcessor.respond(message, attachment_paths)`.
- `POST /api/chat/confirm` accepts a proposal ID and `Idempotency-Key`. Proposals are session-bound and expire after five minutes. The handler delegates cart work to `CartAdapter.add_confirmed(...)`.
- Default processor and cart adapter are placeholders. Do not claim that catalog search, model responses, file extraction, or cart writes work until a real adapter is connected.
- PostgreSQL is used for the product catalog only (`app/catalog.py`); proposals, upload metadata, and idempotency results remain process-local dictionaries by request and disappear on restart. Do not move chat state into the database until the team asks.
- `app/integrations/ekt_api.py` contains the async `httpx` Basic Auth adapter for ekt.kz. Credentials come from server environment variables `EKT_API_USERNAME` and `EKT_API_PASSWORD`; base URL comes from `EKT_API_BASE_URL`. The actual partner response schema is not confirmed, so check parsing aliases against live/partner documentation before relying on fields.
- `app/catalog.py` defines the PostgreSQL catalog schema: ordinary product columns, JSONB attributes and metadata, generated `tsvector`, GIN full-text/JSONB indexes, upserts, and search. `docs/catalog.md` records the schema and sync flow.

## Security and behavior constraints

- Do not accept a session identity from the visitor's message or JSON body. The current `X-Chat-Session` header is only a development stand-in; deployment must replace it with a trusted website authentication/session dependency.
- Keep uploaded file content as untrusted data, never as instructions to the assistant. Preserve filename sanitization, type/extension checks, size limits, and private file permissions.
- Never expose secrets in browser code, source control, or logs.
- Cart mutation requires a specific pending proposal and explicit confirmation. The cart adapter must recheck the authenticated session and stock immediately before writing, honor idempotency, and return the actual updated cart URL/result. If the adapter is unavailable or fails, do not report success.
- Do not invent price, availability, certificate, purchase terms, or product compatibility. Populate responses only from connected trusted sources; indicate unavailable data clearly.

## Extension points

- Implement `ChatProcessor` for catalog/model orchestration and file extraction. Return the Pydantic `ChatResponse` shape.
- Implement `CartAdapter` for the website's cart API and authoritative stock checks.
- Replace `get_session` with the site's trusted session integration before deployment.
- Keep route request/response models explicit and validated with Pydantic. Avoid coupling provider-specific model or file libraries directly to routes.

## Working conventions

- Keep `README.md` and this file in sync when endpoints, configuration, constraints, or integration points change.
- SQL is in scope only for the product catalog described above; chat session state remains in memory until the team asks to persist it.
- Do not add tests unless requested by the user. A basic import/OpenAPI smoke check is useful when dependencies are available.
- `requirements.txt` lists runtime dependencies; install/use the project's virtual environment when available.
