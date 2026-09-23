import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.catalog import router as catalog_router
from app.api.routes.chat import router as chat_router
from app.api.routes.offers import router as offers_router
from app.api.routes.attachments import router as attachments_router
from app.api.routes.chat_attachments import router as chat_attachments_router
from app.config.database import engine
from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.schemas.errors import ErrorResponse
from app.services.errors import ApplicationError

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("chat_service")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting %s (%s)", settings.app_name, settings.app_env)
    yield
    await engine.dispose()
    logger.info("Stopped %s", settings.app_name)


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.widget_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)
app.include_router(health_router)
app.include_router(catalog_router)
app.include_router(chat_router)
app.include_router(chat_attachments_router)
app.include_router(offers_router)
app.include_router(attachments_router)


@app.exception_handler(ApplicationError)
async def application_error_handler(_: Request, exc: ApplicationError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(code=exc.code, message=str(exc) or "Request failed").model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=str(detail.get("code", "http_error")),
            message=str(detail.get("message", "Request could not be processed")),
        ).model_dump(),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    logger.info("request_validation_failed", extra={"event": "request_validation_failed", "error_count": len(exc.errors())})
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(code="validation_error", message="Request validation failed").model_dump(),
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_application_error", extra={"event": "unhandled_application_error", "error_type": type(exc).__name__})
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(code="internal_error", message="Internal server error").model_dump(),
    )
