"""Read-only employee queries for the Telegram weekly report flow.

This module intentionally contains no write operation. It resolves the
employee from their Telegram account, lists only their assigned tasks,
and attaches the single approved weekly plan that covers a given date.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Employee,
    Project,
    Task,
    TaskAssignment,
    WeeklyTaskPlan,
)
from app.schemas.weekly_plan import WeeklyPlanStatus
from app.services.exceptions import NotFoundError
from app.services.task_service import list_employee_tasks


@dataclass(frozen=True)
class EmployeeWeeklyPlan:
    """The approved weekly target an employee may reference in a report."""

    id: int
    week_start_date: date
    week_end_date: date
    target_description: str
    target_completion_percentage: int | None


@dataclass(frozen=True)
class EmployeeTaskContext:
    """An assigned task plus the approved plan covering the asked date.

    ``plan_conflict`` is True when more than one approved plan covers the
    same date. In that case ``weekly_plan`` stays None so a report is
    never attached to an ambiguous target.
    """

    task_id: int
    title: str
    project_id: int
    project_name: str
    planned_start_date: date | None
    planned_due_date: date | None
    weekly_plan: EmployeeWeeklyPlan | None
    plan_conflict: bool = False

    @property
    def has_plan(self) -> bool:
        return self.weekly_plan is not None


async def get_active_employee_by_telegram_id(
    session: AsyncSession,
    telegram_user_id: int,
) -> Employee | None:
    """Return the active employee linked to a Telegram account."""

    return await session.scalar(
        select(Employee).where(
            Employee.telegram_user_id == telegram_user_id,
            Employee.is_active.is_(True),
        )
    )


def _to_weekly_plan(plan: WeeklyTaskPlan) -> EmployeeWeeklyPlan:
    return EmployeeWeeklyPlan(
        id=plan.id,
        week_start_date=plan.week_start_date,
        week_end_date=plan.week_end_date,
        target_description=plan.target_description,
        target_completion_percentage=plan.target_completion_percentage,
    )


def _resolve_plan(
    plans: list[WeeklyTaskPlan],
) -> tuple[EmployeeWeeklyPlan | None, bool]:
    """Pick a single unambiguous approved plan, or flag a conflict."""

    if not plans:
        return None, False

    if len(plans) > 1:
        return None, True

    return _to_weekly_plan(plans[0]), False


def _approved_plan_query(
    task_ids: list[int],
    today: date,
):
    return (
        select(WeeklyTaskPlan)
        .where(
            WeeklyTaskPlan.task_id.in_(task_ids),
            WeeklyTaskPlan.status == WeeklyPlanStatus.APPROVED.value,
            WeeklyTaskPlan.week_start_date <= today,
            WeeklyTaskPlan.week_end_date >= today,
        )
        .order_by(
            WeeklyTaskPlan.task_id,
            WeeklyTaskPlan.week_start_date.desc(),
            WeeklyTaskPlan.id.desc(),
        )
    )


async def _approved_plans_by_task(
    session: AsyncSession,
    task_ids: list[int],
    today: date,
) -> dict[int, list[WeeklyTaskPlan]]:
    if not task_ids:
        return {}

    rows = (
        await session.execute(
            _approved_plan_query(task_ids, today)
        )
    ).scalars().all()

    grouped: dict[int, list[WeeklyTaskPlan]] = {}

    for plan in rows:
        grouped.setdefault(plan.task_id, []).append(plan)

    return grouped


def _build_context(
    task_id: int,
    title: str,
    project_id: int,
    project_name: str,
    planned_start_date: date | None,
    planned_due_date: date | None,
    plans: list[WeeklyTaskPlan],
) -> EmployeeTaskContext:
    weekly_plan, plan_conflict = _resolve_plan(plans)

    return EmployeeTaskContext(
        task_id=task_id,
        title=title,
        project_id=project_id,
        project_name=project_name,
        planned_start_date=planned_start_date,
        planned_due_date=planned_due_date,
        weekly_plan=weekly_plan,
        plan_conflict=plan_conflict,
    )


async def list_my_tasks(
    session: AsyncSession,
    employee_id: int,
    today: date,
) -> list[EmployeeTaskContext]:
    """List the employee's assigned tasks with the plan covering ``today``.

    Tasks without an approved plan are still returned. Only approved
    plans are considered; draft, rejected and superseded plans are
    ignored. Conflicting approved plans are flagged, never guessed.
    """

    tasks = await list_employee_tasks(session, employee_id)

    if not tasks:
        return []

    plans_by_task = await _approved_plans_by_task(
        session,
        [task.id for task in tasks],
        today,
    )

    return [
        _build_context(
            task_id=task.id,
            title=task.title,
            project_id=task.project_id,
            project_name=task.project_name,
            planned_start_date=task.planned_start_date,
            planned_due_date=task.planned_due_date,
            plans=plans_by_task.get(task.id, []),
        )
        for task in tasks
    ]


async def get_task_context(
    session: AsyncSession,
    employee_id: int,
    task_id: int,
    today: date,
) -> EmployeeTaskContext:
    """Return one assigned task context or deny access.

    Assignment is verified here, not only by the calling handler, so a
    callback or message cannot read another employee's task by ID.
    """

    row = (
        await session.execute(
            select(Task, Project.name)
            .join(Project, Project.id == Task.project_id)
            .join(
                TaskAssignment,
                TaskAssignment.task_id == Task.id,
            )
            .where(
                Task.id == task_id,
                TaskAssignment.employee_id == employee_id,
            )
        )
    ).one_or_none()

    if row is None:
        raise NotFoundError(
            "Görev bulunamadı veya bu göreve atanmış değilsiniz."
        )

    task, project_name = row

    plans_by_task = await _approved_plans_by_task(
        session,
        [task.id],
        today,
    )

    return _build_context(
        task_id=task.id,
        title=task.title,
        project_id=task.project_id,
        project_name=project_name,
        planned_start_date=task.planned_start_date,
        planned_due_date=task.planned_due_date,
        plans=plans_by_task.get(task.id, []),
    )
