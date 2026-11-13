from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Employee,
    Project,
    Task,
    TaskAssignment,
    TaskUpdate,
)
from app.schemas.common import Page
from app.schemas.employee import EmployeeRead
from app.schemas.employee_detail import EmployeeDetail
from app.schemas.project import ProjectOption
from app.services.exceptions import ConflictError, NotFoundError
from app.services.task_service import list_employee_tasks


def _task_count_subquery():
    return (
        select(func.count(TaskAssignment.task_id))
        .where(TaskAssignment.employee_id == Employee.id)
        .correlate(Employee)
        .scalar_subquery()
    )


def _project_count_subquery():
    return (
        select(func.count(func.distinct(Task.project_id)))
        .select_from(TaskAssignment)
        .join(Task, Task.id == TaskAssignment.task_id)
        .where(TaskAssignment.employee_id == Employee.id)
        .correlate(Employee)
        .scalar_subquery()
    )


def _to_employee_read(
    employee: Employee,
    task_count: int,
    project_count: int,
) -> EmployeeRead:
    return EmployeeRead(
        id=employee.id,
        full_name=employee.full_name,
        role=employee.role,
        is_active=employee.is_active,
        telegram_user_id=employee.telegram_user_id,
        created_at=employee.created_at,
        task_count=task_count or 0,
        project_count=project_count or 0,
    )


async def list_employees(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    search: str | None = None,
    is_active: bool | None = None,
) -> Page[EmployeeRead]:
    filters = []

    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                Employee.full_name.ilike(pattern),
                Employee.role.ilike(pattern),
            )
        )

    if is_active is not None:
        filters.append(Employee.is_active == is_active)

    total = int(
        (
            await session.execute(
                select(func.count(Employee.id)).where(*filters)
            )
        ).scalar_one()
    )

    stmt = (
        select(
            Employee,
            _task_count_subquery().label("task_count"),
            _project_count_subquery().label("project_count"),
        )
        .where(*filters)
        .order_by(
            Employee.is_active.desc(),
            Employee.full_name.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    rows = (await session.execute(stmt)).all()

    items = [
        _to_employee_read(employee, task_count, project_count)
        for employee, task_count, project_count in rows
    ]

    return Page[EmployeeRead](
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
    )


async def get_employee_detail(
    session: AsyncSession,
    employee_id: int,
) -> EmployeeDetail:
    employee = await session.get(Employee, employee_id)

    if employee is None:
        raise NotFoundError("Çalışan bulunamadı.")

    task_count = int(
        (
            await session.execute(
                select(func.count(TaskAssignment.task_id)).where(
                    TaskAssignment.employee_id == employee_id
                )
            )
        ).scalar_one()
    )
    project_count = int(
        (
            await session.execute(
                select(func.count(func.distinct(Task.project_id)))
                .select_from(TaskAssignment)
                .join(Task, Task.id == TaskAssignment.task_id)
                .where(TaskAssignment.employee_id == employee_id)
            )
        ).scalar_one()
    )

    assigned_tasks = await list_employee_tasks(session, employee_id)

    project_result = await session.execute(
        select(Project)
        .join(Task, Task.project_id == Project.id)
        .join(TaskAssignment, TaskAssignment.task_id == Task.id)
        .where(TaskAssignment.employee_id == employee_id)
        .distinct()
        .order_by(Project.name.asc())
    )

    projects = [
        ProjectOption(id=project.id, name=project.name)
        for project in project_result.scalars().unique()
    ]

    return EmployeeDetail(
        id=employee.id,
        full_name=employee.full_name,
        role=employee.role,
        is_active=employee.is_active,
        telegram_user_id=employee.telegram_user_id,
        created_at=employee.created_at,
        task_count=task_count,
        project_count=project_count,
        assigned_tasks=assigned_tasks,
        projects=projects,
    )


async def list_active_employee_options(
    session: AsyncSession,
) -> list[Employee]:
    result = await session.execute(
        select(Employee)
        .where(Employee.is_active.is_(True))
        .order_by(Employee.full_name.asc())
    )
    return list(result.scalars())


async def _employee_report_count(
    session: AsyncSession,
    employee_id: int,
) -> int:
    """Count reports where the employee is the author or the reviewer."""

    return int(
        (
            await session.execute(
                select(func.count(func.distinct(TaskUpdate.id))).where(
                    or_(
                        TaskUpdate.employee_id == employee_id,
                        TaskUpdate.reviewed_by_employee_id == employee_id,
                    )
                )
            )
        ).scalar_one()
    )


async def delete_employee(
    session: AsyncSession,
    employee_id: int,
) -> None:
    """Delete an employee and their task assignments.

    Reports are historical records and are never deleted implicitly. An
    employee referenced by a report (as author or reviewer) cannot be
    deleted until those reports are removed explicitly. Registration
    requests are preserved by the existing ``ON DELETE SET NULL`` foreign
    key, so deleting an employee never deletes a request or the employee
    linked from it.
    """

    employee = await session.get(Employee, employee_id)

    if employee is None:
        raise NotFoundError("Çalışan bulunamadı.")

    report_count = await _employee_report_count(session, employee_id)

    if report_count > 0:
        raise ConflictError(
            f"Bu çalışana bağlı {report_count} iş raporu bulunuyor. "
            "Rapor geçmişinin korunması için çalışan silinemez. "
            "Lütfen önce ilgili raporları silin."
        )

    try:
        await session.execute(
            delete(TaskAssignment).where(
                TaskAssignment.employee_id == employee_id
            )
        )
        await session.execute(
            delete(Employee).where(Employee.id == employee_id)
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
