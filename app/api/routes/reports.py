from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, require_admin
from app.schemas.report import ReportDetail, ReportListResponse
from app.schemas.work_update import WorkStatus
from app.services import report_service


router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    project_id: int | None = Query(default=None, ge=1),
    employee_id: int | None = Query(default=None, ge=1),
    task_id: int | None = Query(default=None, ge=1),
    report_status: WorkStatus | None = Query(
        default=None,
        alias="status",
    ),
    has_blocker: bool | None = Query(default=None),
    has_delay: bool | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> ReportListResponse:
    return await report_service.list_reports(
        session,
        page=page,
        page_size=page_size,
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        employee_id=employee_id,
        task_id=task_id,
        status=report_status,
        has_blocker=has_blocker,
        has_delay=has_delay,
    )


@router.get("/{report_id}", response_model=ReportDetail)
async def report_detail(
    report_id: int,
    session: AsyncSession = Depends(get_db),
) -> ReportDetail:
    return await report_service.get_report(session, report_id)


@router.delete(
    "/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_report(
    report_id: int,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await report_service.delete_report(session, report_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
