"""Employee queries and confirmed report persistence.

The read helpers resolve the employee from their Telegram account, list
only their assigned tasks, and attach the single approved weekly plan
that covers a given date.

``create_task_update`` persists a report the employee has explicitly
confirmed. It never changes the task or its weekly plan.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Employee,
    Project,
    Task,
    TaskAssignment,
    TaskUpdate,
    WeeklyTaskPlan,
)
from app.schemas.work_update import ProgressScope, WorkUpdate
from app.schemas.weekly_plan import WeeklyPlanStatus
from app.services.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.services.progress import compute_overall_progress
from app.services.task_service import list_employee_tasks
from app.services.week_utils import (
    istanbul_day_start_utc,
    istanbul_today,
    week_contains,
)


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


async def _find_update_by_telegram_message(
    session: AsyncSession,
    telegram_chat_id: int,
    telegram_message_id: int,
) -> int | None:
    return await session.scalar(
        select(TaskUpdate.id).where(
            TaskUpdate.telegram_chat_id == telegram_chat_id,
            TaskUpdate.telegram_message_id == telegram_message_id,
        )
    )


def _is_duplicate_message_error(exc: IntegrityError) -> bool:
    """Return True only for the Telegram source-message unique index."""

    original = exc.orig
    constraint = getattr(original, "constraint_name", None)

    if constraint == "uq_task_updates_telegram_message":
        return True

    return "uq_task_updates_telegram_message" in str(original)


async def get_progress_baseline(
    session: AsyncSession,
    *,
    task_id: int,
    week_start_date: date,
    task_planned_start_date: date | None,
) -> int | None:
    """Return the real overall task progress at the start of a week.

    Only an approved earlier ``TaskUpdate`` that actually contains a
    percentage is used. A previous weekly target is never treated as
    achieved progress. When no earlier report exists, zero is accepted
    only for a task that starts in this week. Otherwise the baseline is
    unknown and no conversion may be made.
    """

    previous = await session.scalar(
        select(TaskUpdate.completion_percentage)
        .where(
            TaskUpdate.task_id == task_id,
            TaskUpdate.review_status == "approved",
            TaskUpdate.completion_percentage.is_not(None),
            TaskUpdate.received_at
            < istanbul_day_start_utc(week_start_date),
        )
        .order_by(
            TaskUpdate.received_at.desc(),
            TaskUpdate.id.desc(),
        )
        .limit(1)
    )

    if previous is not None:
        return previous

    if (
        task_planned_start_date is not None
        and task_planned_start_date >= week_start_date
    ):
        return 0

    return None


async def create_task_update(
    session: AsyncSession,
    *,
    telegram_user_id: int,
    telegram_chat_id: int,
    telegram_message_id: int,
    task_id: int,
    original_message: str,
    draft: WorkUpdate,
    weekly_plan_id: int | None = None,
    reported_eta_date: date | None = None,
    ai_model: str | None = None,
    today: date | None = None,
) -> TaskUpdate:
    """Persist an employee-confirmed AI report as a new ``task_updates`` row.

    Call this only after the employee has reviewed and explicitly
    confirmed the AI draft. The stored review fields represent that
    employee approval, not an administrator decision.

    ``telegram_message_id`` is the employee's own source report message
    (the text or voice message), never the later approval callback
    message. ``original_message`` keeps that report's original text.

    The service re-resolves the employee, the task assignment and the
    weekly plan from the database; nothing supplied by the caller is
    trusted as an authorization decision. It only inserts a row, never
    updates or deletes tasks, plans or previous reports, and it does not
    commit: the caller owns the transaction boundary.
    """

    today_value = today or istanbul_today()

    employee = await get_active_employee_by_telegram_id(
        session,
        telegram_user_id,
    )

    if employee is None:
        raise NotFoundError(
            "Aktif çalışan kaydı bulunamadı. "
            "Lütfen /register ile kayıt talebi oluşturun."
        )

    assigned_task_id = await session.scalar(
        select(TaskAssignment.task_id).where(
            TaskAssignment.task_id == task_id,
            TaskAssignment.employee_id == employee.id,
        )
    )

    if assigned_task_id is None:
        raise NotFoundError(
            "Görev bulunamadı veya bu göreve atanmış değilsiniz."
        )

    plan: WeeklyTaskPlan | None = None

    if weekly_plan_id is not None:
        plan = await session.get(WeeklyTaskPlan, weekly_plan_id)

        if plan is None:
            raise NotFoundError("Haftalık plan bulunamadı.")

        if plan.task_id != task_id:
            raise ValidationError(
                "Seçilen haftalık plan bu göreve ait değil."
            )

        if plan.status != WeeklyPlanStatus.APPROVED.value:
            raise ValidationError(
                "Yalnızca onaylanmış haftalık planlarla "
                "rapor kaydedilebilir."
            )

        if not week_contains(plan, today_value):
            raise ValidationError(
                "Seçilen haftalık plan bugünü kapsamıyor."
            )

    baseline = None
    weekly_target = None

    if (
        draft.progress_scope is ProgressScope.WEEKLY_PLAN
        and plan is not None
    ):
        weekly_target = plan.target_completion_percentage

        task_planned_start_date = await session.scalar(
            select(Task.planned_start_date).where(Task.id == task_id)
        )

        baseline = await get_progress_baseline(
            session,
            task_id=task_id,
            week_start_date=plan.week_start_date,
            task_planned_start_date=task_planned_start_date,
        )

    completion_percentage = compute_overall_progress(
        reported=draft.reported_progress_percentage,
        scope=draft.progress_scope,
        baseline=baseline,
        weekly_target=weekly_target,
    )

    if (
        completion_percentage is None
        and draft.progress_scope is ProgressScope.OVERALL_TASK
    ):
        # Accept a legacy overall draft that only filled the final field.
        completion_percentage = draft.completion_percentage

    existing_id = await _find_update_by_telegram_message(
        session,
        telegram_chat_id,
        telegram_message_id,
    )

    if existing_id is not None:
        raise ConflictError(
            "Bu Telegram mesajı için zaten bir rapor kaydedilmiş."
        )

    update = TaskUpdate(
        task_id=task_id,
        weekly_plan_id=weekly_plan_id,
        employee_id=employee.id,
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_chat_id,
        telegram_message_id=telegram_message_id,
        original_message=original_message,
        task_reference_text=draft.task_reference_text,
        status=draft.status.value,
        completion_percentage=completion_percentage,
        blocker=draft.blocker,
        delay_reason=draft.delay_reason,
        next_step=draft.next_step,
        reported_eta_text=draft.reported_eta_text,
        reported_eta_date=reported_eta_date,
        summary=draft.summary,
        review_status="approved",
        reviewed_by_employee_id=employee.id,
        reviewed_at=datetime.now(timezone.utc),
        ai_model=ai_model,
    )

    try:
        # A savepoint keeps the surrounding transaction usable when the
        # unique index rejects a concurrent duplicate.
        async with session.begin_nested():
            session.add(update)
            await session.flush()
    except IntegrityError as exc:
        if _is_duplicate_message_error(exc):
            raise ConflictError(
                "Bu Telegram mesajı için zaten bir rapor kaydedilmiş."
            ) from exc

        raise

    return update
