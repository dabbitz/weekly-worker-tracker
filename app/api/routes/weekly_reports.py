from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, require_admin
from app.schemas.weekly_report import (
    WeeklyManagerReportStatus,
    WeeklyReportCreate,
    WeeklyReportDetail,
    WeeklyReportListResponse,
    WeeklyReportPeriodsResponse,
    WeeklyReportPreview,
)
from app.services import weekly_report_service


router = APIRouter(
    prefix="/weekly-reports",
    tags=["weekly-reports"],
    dependencies=[Depends(require_admin)],
)


@router.get("/periods", response_model=WeeklyReportPeriodsResponse)
async def list_periods(
    weeks: int = Query(default=12, ge=1, le=52),
):
    return weekly_report_service.get_periods(weeks)


@router.get("/preview", response_model=WeeklyReportPreview)
async def preview_report(
    week_start_date: date = Query(...),
    session: AsyncSession = Depends(get_db),
):
    return await weekly_report_service.get_preview(
        session,
        week_start_date,
    )


@router.get("", response_model=WeeklyReportListResponse)
async def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    week_start_date: date | None = Query(default=None),
    report_status: WeeklyManagerReportStatus | None = Query(
        default=None,
        alias="status",
    ),
    session: AsyncSession = Depends(get_db),
):
    return await weekly_report_service.list_reports(
        session,
        page=page,
        page_size=page_size,
        week_start_date=week_start_date,
        status=report_status,
    )


@router.post(
    "",
    response_model=WeeklyReportDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_report(
    payload: WeeklyReportCreate,
    session: AsyncSession = Depends(get_db),
):
    return await weekly_report_service.create_report(session, payload)


@router.get("/{report_id}", response_model=WeeklyReportDetail)
async def get_report(
    report_id: int,
    session: AsyncSession = Depends(get_db),
):
    return await weekly_report_service.get_report(session, report_id)


@router.post(
    "/{report_id}/retry",
    response_model=WeeklyReportDetail,
)
async def retry_report(
    report_id: int,
    session: AsyncSession = Depends(get_db),
):
    return await weekly_report_service.retry_report(
        session,
        report_id,
    )


@router.delete(
    "/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_report(
    report_id: int,
    session: AsyncSession = Depends(get_db),
):
    await weekly_report_service.delete_report(session, report_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
