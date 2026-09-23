from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def database_is_available(session: AsyncSession) -> bool:
    await session.execute(text("SELECT 1"))
    return True
