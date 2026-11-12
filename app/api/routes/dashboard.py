from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, require_admin
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard_service import get_dashboard_summary


router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_admin)],
)


@router.get("/summary", response_model=DashboardSummary)
async def summary(
    session: AsyncSession = Depends(get_db),
) -> DashboardSummary:
    return await get_dashboard_summary(session)
