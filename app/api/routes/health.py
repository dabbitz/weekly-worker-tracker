from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.api.dependencies import get_db


router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    session: AsyncSession = Depends(get_db),
):
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "degraded",
                "service": "worktrack-api",
                "database": "unavailable",
            },
        )

    return {
        "status": "ok",
        "service": "worktrack-api",
        "database": "ok",
    }
