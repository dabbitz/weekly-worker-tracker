from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Employee,
    Project,
    Task,
    TaskAssignment,
)
from app.schemas.common import Page
from app.schemas.employee import EmployeeSummary
from app.schemas.project import (
    ProjectCreate,
    ProjectDetail,
    ProjectOption,
    ProjectRead,
    ProjectUpdate,
)
from app.services.exceptions import NotFoundError, ValidationError
from app.services.task_service import list_project_tasks


def _task_count_subquery():
    return (
        select(func.count(Task.id))
        .where(Task.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )


def _employee_count_subquery():
    return (
        select(func.count(func.distinct(TaskAssignment.employee_id)))
        .select_from(TaskAssignment)
        .join(Task, Task.id == TaskAssignment.task_id)
        .where(Task.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )


def _clean_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned:
        raise ValidationError("Proje adı boş olamaz.")
    return cleaned


def _to_project_read(
    project: Project,
    task_count: int,
    employee_count: int,
) -> ProjectRead:
    return ProjectRead(
        id=project.id,
        name=project.name,
        description=project.description,
        location=project.location,
        expected_completion_date=project.expected_completion_date,
        created_at=project.created_at,
        task_count=task_count or 0,
        employee_count=employee_count or 0,
    )


async def list_projects(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    search: str | None = None,
) -> Page[ProjectRead]:
    filters = []

    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                Project.name.ilike(pattern),
                Project.location.ilike(pattern),
                Project.description.ilike(pattern),
            )
        )

    total = int(
        (
            await session.execute(
                select(func.count(Project.id)).where(*filters)
            )
        ).scalar_one()
    )

    stmt = (
        select(
            Project,
            _task_count_subquery().label("task_count"),
            _employee_count_subquery().label("employee_count"),
        )
        .where(*filters)
        .order_by(Project.created_at.desc(), Project.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    rows = (await session.execute(stmt)).all()

    items = [
        _to_project_read(project, task_count, employee_count)
        for project, task_count, employee_count in rows
    ]

    return Page[ProjectRead](
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
    )


async def _get_counts(
    session: AsyncSession,
    project_id: int,
) -> tuple[int, int]:
    task_count = int(
        (
            await session.execute(
                select(func.count(Task.id)).where(
                    Task.project_id == project_id
                )
            )
        ).scalar_one()
    )
    employee_count = int(
        (
            await session.execute(
                select(
                    func.count(func.distinct(TaskAssignment.employee_id))
                )
                .select_from(TaskAssignment)
                .join(Task, Task.id == TaskAssignment.task_id)
                .where(Task.project_id == project_id)
            )
        ).scalar_one()
    )
    return task_count, employee_count


async def get_project(
    session: AsyncSession,
    project_id: int,
) -> ProjectRead:
    project = await session.get(Project, project_id)

    if project is None:
        raise NotFoundError("Proje bulunamadı.")

    task_count, employee_count = await _get_counts(session, project_id)
    return _to_project_read(project, task_count, employee_count)


async def get_project_detail(
    session: AsyncSession,
    project_id: int,
) -> ProjectDetail:
    project = await session.get(Project, project_id)

    if project is None:
        raise NotFoundError("Proje bulunamadı.")

    tasks = await list_project_tasks(session, project_id)

    employee_result = await session.execute(
        select(Employee)
        .join(TaskAssignment, TaskAssignment.employee_id == Employee.id)
        .join(Task, Task.id == TaskAssignment.task_id)
        .where(Task.project_id == project_id)
        .distinct()
        .order_by(Employee.is_active.desc(), Employee.full_name.asc())
    )
    employees = [
        EmployeeSummary.model_validate(employee)
        for employee in employee_result.scalars().unique()
    ]

    return ProjectDetail(
        id=project.id,
        name=project.name,
        description=project.description,
        location=project.location,
        expected_completion_date=project.expected_completion_date,
        created_at=project.created_at,
        task_count=len(tasks),
        employee_count=len(employees),
        tasks=tasks,
        employees=employees,
    )


async def get_project_employees(
    session: AsyncSession,
    project_id: int,
) -> list[EmployeeSummary]:
    exists = await session.scalar(
        select(Project.id).where(Project.id == project_id)
    )

    if exists is None:
        raise NotFoundError("Proje bulunamadı.")

    result = await session.execute(
        select(Employee)
        .join(TaskAssignment, TaskAssignment.employee_id == Employee.id)
        .join(Task, Task.id == TaskAssignment.task_id)
        .where(Task.project_id == project_id)
        .distinct()
        .order_by(Employee.is_active.desc(), Employee.full_name.asc())
    )

    return [
        EmployeeSummary.model_validate(employee)
        for employee in result.scalars().unique()
    ]


async def create_project(
    session: AsyncSession,
    payload: ProjectCreate,
) -> ProjectRead:
    project = Project(
        name=_clean_name(payload.name),
        description=payload.description,
        location=payload.location,
        expected_completion_date=payload.expected_completion_date,
    )

    session.add(project)
    await session.commit()
    await session.refresh(project)

    return _to_project_read(project, 0, 0)


async def update_project(
    session: AsyncSession,
    project_id: int,
    payload: ProjectUpdate,
) -> ProjectRead:
    project = await session.get(Project, project_id)

    if project is None:
        raise NotFoundError("Proje bulunamadı.")

    fields = payload.model_dump(exclude_unset=True)

    if "name" in fields and fields["name"] is not None:
        project.name = _clean_name(fields["name"])

    if "description" in fields:
        project.description = fields["description"]

    if "location" in fields:
        project.location = fields["location"]

    if "expected_completion_date" in fields:
        project.expected_completion_date = fields[
            "expected_completion_date"
        ]

    await session.commit()
    await session.refresh(project)

    task_count, employee_count = await _get_counts(session, project_id)
    return _to_project_read(project, task_count, employee_count)


async def list_project_options(
    session: AsyncSession,
) -> list[ProjectOption]:
    result = await session.execute(
        select(Project).order_by(Project.name.asc())
    )
    return [
        ProjectOption(id=project.id, name=project.name)
        for project in result.scalars()
    ]
