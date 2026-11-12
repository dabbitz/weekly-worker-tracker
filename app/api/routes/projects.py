from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, require_admin
from app.schemas.common import Page
from app.schemas.employee import EmployeeSummary
from app.schemas.project import (
    ProjectCreate,
    ProjectDetail,
    ProjectOption,
    ProjectRead,
    ProjectUpdate,
)
from app.schemas.task import TaskRead
from app.services import project_service
from app.services.task_service import list_project_tasks


router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=Page[ProjectRead])
async def list_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    session: AsyncSession = Depends(get_db),
) -> Page[ProjectRead]:
    return await project_service.list_projects(
        session,
        page=page,
        page_size=page_size,
        search=search,
    )


@router.get("/options", response_model=list[ProjectOption])
async def project_options(
    session: AsyncSession = Depends(get_db),
) -> list[ProjectOption]:
    return await project_service.list_project_options(session)


@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    payload: ProjectCreate,
    session: AsyncSession = Depends(get_db),
) -> ProjectRead:
    return await project_service.create_project(session, payload)


@router.get("/{project_id}", response_model=ProjectDetail)
async def project_detail(
    project_id: int,
    session: AsyncSession = Depends(get_db),
) -> ProjectDetail:
    return await project_service.get_project_detail(session, project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    session: AsyncSession = Depends(get_db),
) -> ProjectRead:
    return await project_service.update_project(
        session,
        project_id,
        payload,
    )


@router.get("/{project_id}/employees", response_model=list[EmployeeSummary])
async def project_employees(
    project_id: int,
    session: AsyncSession = Depends(get_db),
) -> list[EmployeeSummary]:
    return await project_service.get_project_employees(
        session,
        project_id,
    )


@router.get("/{project_id}/tasks", response_model=list[TaskRead])
async def project_tasks(
    project_id: int,
    session: AsyncSession = Depends(get_db),
) -> list[TaskRead]:
    return await list_project_tasks(session, project_id)
