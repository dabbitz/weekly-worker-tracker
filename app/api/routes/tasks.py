from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, require_admin
from app.schemas.common import Page
from app.schemas.task import (
    AssignmentUpdate,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)
from app.services import task_service


router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=Page[TaskRead])
async def list_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    project_id: int | None = Query(default=None, ge=1),
    employee_id: int | None = Query(default=None, ge=1),
    session: AsyncSession = Depends(get_db),
) -> Page[TaskRead]:
    return await task_service.list_tasks(
        session,
        page=page,
        page_size=page_size,
        search=search,
        project_id=project_id,
        employee_id=employee_id,
    )


@router.post(
    "",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    payload: TaskCreate,
    session: AsyncSession = Depends(get_db),
) -> TaskRead:
    return await task_service.create_task(session, payload)


@router.get("/{task_id}", response_model=TaskRead)
async def task_detail(
    task_id: int,
    session: AsyncSession = Depends(get_db),
) -> TaskRead:
    return await task_service.get_task(session, task_id)


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    session: AsyncSession = Depends(get_db),
) -> TaskRead:
    return await task_service.update_task(
        session,
        task_id,
        payload,
    )


@router.put("/{task_id}/assignments", response_model=TaskRead)
async def set_assignments(
    task_id: int,
    payload: AssignmentUpdate,
    session: AsyncSession = Depends(get_db),
) -> TaskRead:
    return await task_service.set_task_assignments(
        session,
        task_id,
        payload,
    )
