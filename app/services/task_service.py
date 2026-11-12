from datetime import date

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import (
    Employee,
    Project,
    Task,
    TaskAssignment,
    WeeklyTaskPlan,
)
from app.schemas.common import Page
from app.schemas.employee import EmployeeSummary
from app.schemas.task import AssignmentUpdate, TaskCreate, TaskRead, TaskUpdate
from app.services.exceptions import ConflictError, NotFoundError, ValidationError


def _plan_count_subquery():
    return (
        select(func.count(WeeklyTaskPlan.id))
        .where(WeeklyTaskPlan.task_id == Task.id)
        .correlate(Task)
        .scalar_subquery()
    )


def _base_task_query() -> Select:
    return (
        select(
            Task,
            Project.name.label("project_name"),
            _plan_count_subquery().label("weekly_plan_count"),
        )
        .join(Project, Project.id == Task.project_id)
        .options(
            selectinload(Task.assignments).selectinload(
                TaskAssignment.employee
            )
        )
    )


def serialize_task(
    task: Task,
    project_name: str,
    weekly_plan_count: int = 0,
) -> TaskRead:
    employees = sorted(
        (assignment.employee for assignment in task.assignments),
        key=lambda employee: (
            not employee.is_active,
            employee.full_name.casefold(),
        ),
    )

    return TaskRead(
        id=task.id,
        project_id=task.project_id,
        project_name=project_name,
        title=task.title,
        description=task.description,
        planned_start_date=task.planned_start_date,
        planned_start_weekday=task.planned_start_weekday,
        planned_due_date=task.planned_due_date,
        planned_due_weekday=task.planned_due_weekday,
        created_at=task.created_at,
        assigned_employees=[
            EmployeeSummary.model_validate(employee)
            for employee in employees
        ],
        weekly_plan_count=weekly_plan_count or 0,
    )


def _validate_dates(
    planned_start_date: date | None,
    planned_due_date: date | None,
) -> None:
    if (
        planned_start_date is not None
        and planned_due_date is not None
        and planned_start_date > planned_due_date
    ):
        raise ValidationError(
            "Planlanan başlangıç tarihi, planlanan bitiş tarihinden "
            "sonra olamaz."
        )


def _clean_title(title: str) -> str:
    cleaned = " ".join(title.split())
    if not cleaned:
        raise ValidationError("Görev başlığı boş olamaz.")
    return cleaned


async def get_task(
    session: AsyncSession,
    task_id: int,
) -> TaskRead:
    result = await session.execute(
        _base_task_query().where(Task.id == task_id)
    )
    row = result.one_or_none()

    if row is None:
        raise NotFoundError("Görev bulunamadı.")

    task, project_name, weekly_plan_count = row
    return serialize_task(task, project_name, weekly_plan_count)


async def list_tasks(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    search: str | None = None,
    project_id: int | None = None,
    employee_id: int | None = None,
) -> Page[TaskRead]:
    filters = []

    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                Task.title.ilike(pattern),
                Project.name.ilike(pattern),
            )
        )

    if project_id is not None:
        filters.append(Task.project_id == project_id)

    if employee_id is not None:
        filters.append(
            Task.assignments.any(
                TaskAssignment.employee_id == employee_id
            )
        )

    total_stmt = (
        select(func.count(Task.id))
        .select_from(Task)
        .join(Project, Project.id == Task.project_id)
        .where(*filters)
    )
    total = int((await session.execute(total_stmt)).scalar_one())

    stmt = _base_task_query().where(*filters)

    if project_id is not None:
        stmt = stmt.order_by(
            Task.planned_start_date.asc().nulls_last(),
            Task.created_at.desc(),
        )
    else:
        stmt = stmt.order_by(Task.created_at.desc(), Task.id.desc())

    rows = (
        await session.execute(
            stmt.offset((page - 1) * page_size).limit(page_size)
        )
    ).all()

    items = [
        serialize_task(task, project_name, weekly_plan_count)
        for task, project_name, weekly_plan_count in rows
    ]

    return Page[TaskRead](
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
    )


async def list_employee_tasks(
    session: AsyncSession,
    employee_id: int,
) -> list[TaskRead]:
    rows = (
        await session.execute(
            _base_task_query()
            .where(
                Task.id.in_(
                    select(TaskAssignment.task_id).where(
                        TaskAssignment.employee_id == employee_id
                    )
                )
            )
            .order_by(
                Task.planned_due_date.asc().nulls_last(),
                Task.created_at.desc(),
            )
        )
    ).all()

    return [
        serialize_task(task, project_name, weekly_plan_count)
        for task, project_name, weekly_plan_count in rows
    ]


async def list_project_tasks(
    session: AsyncSession,
    project_id: int,
) -> list[TaskRead]:
    rows = (
        await session.execute(
            _base_task_query()
            .where(Task.project_id == project_id)
            .order_by(
                Task.planned_start_date.asc().nulls_last(),
                Task.created_at.desc(),
            )
        )
    ).all()

    return [
        serialize_task(task, project_name, weekly_plan_count)
        for task, project_name, weekly_plan_count in rows
    ]


async def _ensure_project(
    session: AsyncSession,
    project_id: int,
) -> None:
    exists = await session.scalar(
        select(Project.id).where(Project.id == project_id)
    )
    if exists is None:
        raise NotFoundError("Proje bulunamadı.")


async def _resolve_employees(
    session: AsyncSession,
    requested_ids: list[int],
    current_ids: set[int],
) -> list[Employee]:
    unique_ids = list(dict.fromkeys(requested_ids))

    if not unique_ids:
        return []

    result = await session.execute(
        select(Employee).where(Employee.id.in_(unique_ids))
    )
    employees = {employee.id: employee for employee in result.scalars()}

    missing = [str(employee_id) for employee_id in unique_ids if employee_id not in employees]

    if missing:
        raise ValidationError(
            "Şu çalışanlar bulunamadı: " + ", ".join(missing)
        )

    inactive_new = [
        employees[employee_id].full_name
        for employee_id in unique_ids
        if not employees[employee_id].is_active
        and employee_id not in current_ids
    ]

    if inactive_new:
        raise ValidationError(
            "Pasif çalışanlar yeni bir göreve atanamaz: "
            + ", ".join(inactive_new)
        )

    return [employees[employee_id] for employee_id in unique_ids]


async def create_task(
    session: AsyncSession,
    payload: TaskCreate,
) -> TaskRead:
    await _ensure_project(session, payload.project_id)
    _validate_dates(
        payload.planned_start_date,
        payload.planned_due_date,
    )

    task = Task(
        project_id=payload.project_id,
        title=_clean_title(payload.title),
        description=payload.description,
        planned_start_date=payload.planned_start_date,
        planned_due_date=payload.planned_due_date,
    )

    session.add(task)
    await session.flush()

    employees = await _resolve_employees(
        session,
        payload.employee_ids,
        set(),
    )

    for employee in employees:
        session.add(
            TaskAssignment(task_id=task.id, employee_id=employee.id)
        )

    await session.commit()

    return await get_task(session, task.id)


async def update_task(
    session: AsyncSession,
    task_id: int,
    payload: TaskUpdate,
) -> TaskRead:
    task = await session.get(Task, task_id)

    if task is None:
        raise NotFoundError("Görev bulunamadı.")

    fields = payload.model_dump(exclude_unset=True)

    if "project_id" in fields and fields["project_id"] is not None:
        await _ensure_project(session, fields["project_id"])
        task.project_id = fields["project_id"]

    if "title" in fields and fields["title"] is not None:
        task.title = _clean_title(fields["title"])

    if "description" in fields:
        task.description = fields["description"]

    if "planned_start_date" in fields:
        task.planned_start_date = fields["planned_start_date"]

    if "planned_due_date" in fields:
        task.planned_due_date = fields["planned_due_date"]

    _validate_dates(
        task.planned_start_date,
        task.planned_due_date,
    )

    await session.commit()

    return await get_task(session, task.id)


async def set_task_assignments(
    session: AsyncSession,
    task_id: int,
    payload: AssignmentUpdate,
) -> TaskRead:
    task = await session.get(Task, task_id)

    if task is None:
        raise NotFoundError("Görev bulunamadı.")

    current_result = await session.execute(
        select(TaskAssignment.employee_id).where(
            TaskAssignment.task_id == task_id
        )
    )
    current_ids = set(current_result.scalars().all())

    employees = await _resolve_employees(
        session,
        payload.employee_ids,
        current_ids,
    )
    requested_ids = {employee.id for employee in employees}

    removed_ids = current_ids - requested_ids
    added_ids = requested_ids - current_ids

    for employee_id in removed_ids:
        assignment = await session.get(
            TaskAssignment,
            (task_id, employee_id),
        )
        if assignment is not None:
            await session.delete(assignment)

    for employee_id in added_ids:
        session.add(
            TaskAssignment(task_id=task_id, employee_id=employee_id)
        )

    await session.commit()

    return await get_task(session, task_id)


async def ensure_project_has_no_direct_employee_link() -> None:
    """Guard-rail used by tests and documentation.

    Employee-project relationships are intentionally derived through
    tasks and task_assignments only.
    """

    if hasattr(Project, "employees") or hasattr(Employee, "projects"):
        raise ConflictError(
            "Doğrudan çalışan-proje ilişkisi desteklenmiyor."
        )
