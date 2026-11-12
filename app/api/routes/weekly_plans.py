from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, require_admin
from app.schemas.common import Page
from app.schemas.weekly_plan import (
    WeeklyPlanCreate,
    WeeklyPlanRead,
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
    session: AsyncSession = Depends(get_db),
) -> Page[WeeklyPlanRead]:
    return await weekly_plan_service.list_plans(
        session,
        page=page,
        page_size=page_size,
        task_id=task_id,
        project_id=project_id,
        week_start_date=week_start_date,
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
