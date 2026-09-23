import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.health import router as health_router
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
app.include_router(health_router)


@app.exception_handler(ApplicationError)
async def application_error_handler(_: Request, exc: ApplicationError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(code=exc.code, message=str(exc) or "Request failed").model_dump(),
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(code="internal_error", message="Internal server error").model_dump(),
    )
