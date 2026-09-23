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
