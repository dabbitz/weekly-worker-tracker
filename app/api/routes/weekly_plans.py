from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, require_admin
from app.schemas.common import Page
from app.schemas.weekly_plan import (
    AIPlanGenerateRequest,
    AIPlanGenerateResponse,
    WeeklyPlanApprove,
    WeeklyPlanCreate,
    WeeklyPlanRead,
    WeeklyPlanSource,
    WeeklyPlanStatus,
    WeeklyPlanUpdate,
)
from app.services import weekly_plan_service


router = APIRouter(
    prefix="/weekly-plans",
    tags=["weekly-plans"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=Page[WeeklyPlanRead])
async def list_plans(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    task_id: int | None = Query(default=None, ge=1),
    project_id: int | None = Query(default=None, ge=1),
    week_start_date: date | None = Query(default=None),
    plan_status: WeeklyPlanStatus | None = Query(
        default=None,
        alias="status",
    ),
    source: WeeklyPlanSource | None = Query(default=None),
    generation_id: int | None = Query(default=None, ge=1),
    session: AsyncSession = Depends(get_db),
) -> Page[WeeklyPlanRead]:
    return await weekly_plan_service.list_plans(
        session,
        page=page,
        page_size=page_size,
        task_id=task_id,
        project_id=project_id,
        week_start_date=week_start_date,
        status=plan_status,
        source=source,
        generation_id=generation_id,
    )


@router.post(
    "",
    response_model=WeeklyPlanRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_plan(
    payload: WeeklyPlanCreate,
    session: AsyncSession = Depends(get_db),
) -> WeeklyPlanRead:
    return await weekly_plan_service.create_plan(session, payload)


@router.post(
    "/ai/generate",
    response_model=AIPlanGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_ai_plans(
    payload: AIPlanGenerateRequest,
    session: AsyncSession = Depends(get_db),
) -> AIPlanGenerateResponse:
    return await weekly_plan_service.generate_ai_plans(
        session,
        payload,
    )


@router.get("/{plan_id}", response_model=WeeklyPlanRead)
async def plan_detail(
    plan_id: int,
    session: AsyncSession = Depends(get_db),
) -> WeeklyPlanRead:
    return await weekly_plan_service.get_plan(session, plan_id)


@router.patch("/{plan_id}", response_model=WeeklyPlanRead)
async def update_plan(
    plan_id: int,
    payload: WeeklyPlanUpdate,
    session: AsyncSession = Depends(get_db),
) -> WeeklyPlanRead:
    return await weekly_plan_service.update_plan(
        session,
        plan_id,
        payload,
    )


@router.post("/{plan_id}/approve", response_model=WeeklyPlanRead)
async def approve_plan(
    plan_id: int,
    payload: WeeklyPlanApprove | None = None,
    session: AsyncSession = Depends(get_db),
) -> WeeklyPlanRead:
    return await weekly_plan_service.approve_plan(
        session,
        plan_id,
        replace_existing=bool(payload and payload.replace_existing),
    )


@router.post("/{plan_id}/reject", response_model=WeeklyPlanRead)
async def reject_plan(
    plan_id: int,
    session: AsyncSession = Depends(get_db),
) -> WeeklyPlanRead:
    return await weekly_plan_service.reject_plan(session, plan_id)


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_plan(
    plan_id: int,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await weekly_plan_service.delete_plan(session, plan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
