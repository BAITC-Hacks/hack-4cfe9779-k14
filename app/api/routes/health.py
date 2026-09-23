from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.repositories.health import database_is_available
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(session: AsyncSession = Depends(get_db)) -> HealthResponse:
    try:
        await database_is_available(session)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail={"code": "database_unavailable", "message": "Database is unavailable"}) from exc
    return HealthResponse(status="ok", database="ok")
