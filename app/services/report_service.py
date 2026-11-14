"""Administrator queries and explicit deletions for work reports.

Reports are the persisted ``task_updates`` rows. Listing and reading keep
their related employee, task, project, reviewer and weekly plan data.
Deleting a report removes only that report row: related tasks, plans,
employees and projects are never modified.
"""

from datetime import date, datetime, timedelta

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.database.models import (
    Employee,
    Project,
    Task,
    TaskUpdate,
    WeeklyTaskPlan,
)
from app.schemas.report import (
    ReportDetail,
    ReportListItem,
    ReportListResponse,
    ReportReviewStatus,
    ReportStats,
    ReportWeeklyPlan,
)
from app.schemas.work_update import WorkStatus
from app.services.exceptions import NotFoundError, ValidationError
from app.services.week_utils import istanbul_day_start_utc


def _istanbul_day_start_utc(day: date) -> datetime:
    """Return the UTC instant when ``day`` starts in Istanbul."""

    return istanbul_day_start_utc(day)


def _has_text(expression) -> object:
    """SQL predicate: the text column contains non-whitespace content."""

    return and_(
        expression.is_not(None),
        func.length(func.trim(expression)) > 0,
    )


def _has_no_text(expression) -> object:
    return or_(
        expression.is_(None),
        func.length(func.trim(expression)) == 0,
    )


def _build_filters(
    *,
    date_from: date | None,
    date_to: date | None,
    project_id: int | None,
    employee_id: int | None,
    task_id: int | None,
    status: WorkStatus | None,
    has_blocker: bool | None,
    has_delay: bool | None,
) -> list:
    filters = []

    if date_from is not None:
        filters.append(
            TaskUpdate.received_at >= _istanbul_day_start_utc(date_from)
        )

    if date_to is not None:
        # The end date is inclusive, so compare against the next
        # Istanbul midnight converted to UTC.
        filters.append(
            TaskUpdate.received_at
            < _istanbul_day_start_utc(date_to + timedelta(days=1))
        )

    if project_id is not None:
        filters.append(Task.project_id == project_id)

    if employee_id is not None:
        filters.append(TaskUpdate.employee_id == employee_id)

    if task_id is not None:
        filters.append(TaskUpdate.task_id == task_id)

    if status is not None:
        filters.append(TaskUpdate.status == status.value)

    if has_blocker is True:
        filters.append(_has_text(TaskUpdate.blocker))
    elif has_blocker is False:
        filters.append(_has_no_text(TaskUpdate.blocker))

    if has_delay is True:
        filters.append(_has_text(TaskUpdate.delay_reason))
    elif has_delay is False:
        filters.append(_has_no_text(TaskUpdate.delay_reason))

    return filters


def _stats_statement(filters: list) -> Select:
    blocker_present = _has_text(TaskUpdate.blocker)
    delay_present = _has_text(TaskUpdate.delay_reason)

    return (
        select(
            func.count(TaskUpdate.id).label("total"),
            func.count(TaskUpdate.id)
            .filter(TaskUpdate.status == WorkStatus.BLOCKED.value)
            .label("blocked_count"),
            func.count(TaskUpdate.id)
            .filter(blocker_present)
            .label("with_blocker_count"),
            func.count(TaskUpdate.id)
            .filter(delay_present)
            .label("with_delay_count"),
            func.count(TaskUpdate.id)
            .filter(TaskUpdate.status == WorkStatus.COMPLETED.value)
            .label("completed_count"),
        )
        .select_from(TaskUpdate)
        .outerjoin(Task, Task.id == TaskUpdate.task_id)
        .where(*filters)
    )


def _list_statement(filters: list, *, page: int, page_size: int) -> Select:
    return (
        select(
            TaskUpdate.id,
            TaskUpdate.received_at,
            TaskUpdate.employee_id,
            Employee.full_name.label("employee_name"),
            Task.project_id.label("project_id"),
            Project.name.label("project_name"),
            TaskUpdate.task_id,
            Task.title.label("task_title"),
            TaskUpdate.completion_percentage,
            TaskUpdate.status,
            TaskUpdate.blocker,
            TaskUpdate.delay_reason,
            TaskUpdate.review_status,
            TaskUpdate.weekly_plan_id,
        )
        .select_from(TaskUpdate)
        .outerjoin(Employee, Employee.id == TaskUpdate.employee_id)
        .outerjoin(Task, Task.id == TaskUpdate.task_id)
        .outerjoin(Project, Project.id == Task.project_id)
        .where(*filters)
        .order_by(
            TaskUpdate.received_at.desc(),
            TaskUpdate.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )


def _serialize_list_item(row) -> ReportListItem:
    return ReportListItem(
        id=row["id"],
        received_at=row["received_at"],
        employee_id=row["employee_id"],
        employee_name=row["employee_name"],
        project_id=row["project_id"],
        project_name=row["project_name"],
        task_id=row["task_id"],
        task_title=row["task_title"],
        completion_percentage=row["completion_percentage"],
        status=WorkStatus(row["status"]),
        has_blocker=bool(
            row["blocker"] and row["blocker"].strip()
        ),
        has_delay=bool(
            row["delay_reason"] and row["delay_reason"].strip()
        ),
        review_status=ReportReviewStatus(row["review_status"]),
        weekly_plan_id=row["weekly_plan_id"],
        has_weekly_plan=row["weekly_plan_id"] is not None,
    )


async def list_reports(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    date_from: date | None = None,
    date_to: date | None = None,
    project_id: int | None = None,
    employee_id: int | None = None,
    task_id: int | None = None,
    status: WorkStatus | None = None,
    has_blocker: bool | None = None,
    has_delay: bool | None = None,
) -> ReportListResponse:
    if (
        date_from is not None
        and date_to is not None
        and date_from > date_to
    ):
        raise ValidationError(
            "Başlangıç tarihi, bitiş tarihinden sonra olamaz."
        )

    filters = _build_filters(
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        employee_id=employee_id,
        task_id=task_id,
        status=status,
        has_blocker=has_blocker,
        has_delay=has_delay,
    )

    stats_row = (
        await session.execute(_stats_statement(filters))
    ).mappings().one()

    stats = ReportStats(
        total=int(stats_row["total"]),
        blocked_count=int(stats_row["blocked_count"]),
        with_blocker_count=int(stats_row["with_blocker_count"]),
        with_delay_count=int(stats_row["with_delay_count"]),
        completed_count=int(stats_row["completed_count"]),
    )

    rows = (
        await session.execute(
            _list_statement(
                filters,
                page=page,
                page_size=page_size,
            )
        )
    ).mappings().all()

    total = stats.total

    return ReportListResponse(
        items=[_serialize_list_item(row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
        stats=stats,
    )


async def get_report(
    session: AsyncSession,
    report_id: int,
) -> ReportDetail:
    reviewer = aliased(Employee)

    row = (
        await session.execute(
            select(
                TaskUpdate,
                Employee.full_name.label("employee_name"),
                reviewer.full_name.label("reviewer_name"),
                Task.title.label("task_title"),
                Task.description.label("task_description"),
                Task.project_id.label("project_id"),
                Project.name.label("project_name"),
                WeeklyTaskPlan,
            )
            .select_from(TaskUpdate)
            .outerjoin(Employee, Employee.id == TaskUpdate.employee_id)
            .outerjoin(
                reviewer,
                reviewer.id == TaskUpdate.reviewed_by_employee_id,
            )
            .outerjoin(Task, Task.id == TaskUpdate.task_id)
            .outerjoin(Project, Project.id == Task.project_id)
            .outerjoin(
                WeeklyTaskPlan,
                WeeklyTaskPlan.id == TaskUpdate.weekly_plan_id,
            )
            .where(TaskUpdate.id == report_id)
        )
    ).mappings().one_or_none()

    if row is None:
        raise NotFoundError("Rapor bulunamadı.")

    update = row["TaskUpdate"]
    plan = row["WeeklyTaskPlan"]

    return ReportDetail(
        id=update.id,
        received_at=update.received_at,
        employee_id=update.employee_id,
        employee_name=row["employee_name"],
        project_id=row["project_id"],
        project_name=row["project_name"],
        task_id=update.task_id,
        task_title=row["task_title"],
        completion_percentage=update.completion_percentage,
        status=WorkStatus(update.status),
        has_blocker=bool(
            update.blocker and update.blocker.strip()
        ),
        has_delay=bool(
            update.delay_reason and update.delay_reason.strip()
        ),
        review_status=ReportReviewStatus(update.review_status),
        weekly_plan_id=update.weekly_plan_id,
        has_weekly_plan=update.weekly_plan_id is not None,
        task_description=row["task_description"],
        original_message=update.original_message,
        task_reference_text=update.task_reference_text,
        blocker=update.blocker,
        delay_reason=update.delay_reason,
        next_step=update.next_step,
        reported_eta_text=update.reported_eta_text,
        reported_eta_date=update.reported_eta_date,
        reported_eta_weekday=update.reported_eta_weekday,
        summary=update.summary,
        ai_model=update.ai_model,
        reviewed_at=update.reviewed_at,
        reviewed_by_employee_id=update.reviewed_by_employee_id,
        reviewed_by_employee_name=row["reviewer_name"],
        weekly_plan=(
            ReportWeeklyPlan(
                id=plan.id,
                target_description=plan.target_description,
                target_completion_percentage=(
                    plan.target_completion_percentage
                ),
                week_start_date=plan.week_start_date,
                week_end_date=plan.week_end_date,
                status=plan.status,
            )
            if plan is not None
            else None
        ),
    )


async def delete_report(
    session: AsyncSession,
    report_id: int,
) -> None:
    """Delete only the selected ``TaskUpdate`` row.

    The task, weekly plan, employee and review relationships are left
    untouched. Missing reports return the standard 404 service error.
    """

    report = await session.get(TaskUpdate, report_id)

    if report is None:
        raise NotFoundError("Rapor bulunamadı.")

    await session.delete(report)
    await session.commit()
