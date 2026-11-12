from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Project, Task, WeeklyTaskPlan
from app.schemas.common import Page
from app.schemas.weekly_plan import (
    WeeklyPlanCreate,
    WeeklyPlanRead,
    WeeklyPlanUpdate,
)
from app.services.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)


def _base_plan_query():
    return (
        select(
            WeeklyTaskPlan,
            Task.title.label("task_title"),
            Project.id.label("project_id"),
            Project.name.label("project_name"),
        )
        .join(Task, Task.id == WeeklyTaskPlan.task_id)
        .join(Project, Project.id == Task.project_id)
    )


def _serialize_plan(
    plan: WeeklyTaskPlan,
    task_title: str,
    project_id: int,
    project_name: str,
) -> WeeklyPlanRead:
    return WeeklyPlanRead(
        id=plan.id,
        task_id=plan.task_id,
        task_title=task_title,
        project_id=project_id,
        project_name=project_name,
        week_start_date=plan.week_start_date,
        week_end_date=plan.week_end_date,
        target_description=plan.target_description,
        target_completion_percentage=plan.target_completion_percentage,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def _validate_plan(
    week_start_date,
    week_end_date,
    target_description: str,
) -> None:
    if week_end_date < week_start_date:
        raise ValidationError(
            "Hafta bitiş tarihi, hafta başlangıç tarihinden önce olamaz."
        )

    if not target_description.strip():
        raise ValidationError("Haftalık hedef açıklaması boş olamaz.")


async def _ensure_task(
    session: AsyncSession,
    task_id: int,
) -> None:
    exists = await session.scalar(
        select(Task.id).where(Task.id == task_id)
    )
    if exists is None:
        raise NotFoundError("Görev bulunamadı.")


async def _ensure_unique_week(
    session: AsyncSession,
    task_id: int,
    week_start_date,
    exclude_plan_id: int | None = None,
) -> None:
    stmt = select(WeeklyTaskPlan.id).where(
        WeeklyTaskPlan.task_id == task_id,
        WeeklyTaskPlan.week_start_date == week_start_date,
    )

    if exclude_plan_id is not None:
        stmt = stmt.where(WeeklyTaskPlan.id != exclude_plan_id)

    exists = await session.scalar(stmt)

    if exists is not None:
        raise ConflictError(
            "Bu görev için seçilen haftada zaten bir plan var."
        )


async def get_plan(
    session: AsyncSession,
    plan_id: int,
) -> WeeklyPlanRead:
    row = (
        await session.execute(
            _base_plan_query().where(WeeklyTaskPlan.id == plan_id)
        )
    ).one_or_none()

    if row is None:
        raise NotFoundError("Haftalık plan bulunamadı.")

    plan, task_title, project_id, project_name = row
    return _serialize_plan(
        plan,
        task_title,
        project_id,
        project_name,
    )


async def list_plans(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    task_id: int | None = None,
    project_id: int | None = None,
    week_start_date=None,
) -> Page[WeeklyPlanRead]:
    filters = []

    if task_id is not None:
        filters.append(WeeklyTaskPlan.task_id == task_id)

    if project_id is not None:
        filters.append(Task.project_id == project_id)

    if week_start_date is not None:
        filters.append(
            WeeklyTaskPlan.week_start_date == week_start_date
        )

    total = int(
        (
            await session.execute(
                select(func.count(WeeklyTaskPlan.id))
                .select_from(WeeklyTaskPlan)
                .join(Task, Task.id == WeeklyTaskPlan.task_id)
                .where(*filters)
            )
        ).scalar_one()
    )

    rows = (
        await session.execute(
            _base_plan_query()
            .where(*filters)
            .order_by(
                WeeklyTaskPlan.week_start_date.desc(),
                WeeklyTaskPlan.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items = [
        _serialize_plan(plan, task_title, project_id, project_name)
        for plan, task_title, project_id, project_name in rows
    ]

    return Page[WeeklyPlanRead](
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
    )


async def create_plan(
    session: AsyncSession,
    payload: WeeklyPlanCreate,
) -> WeeklyPlanRead:
    await _ensure_task(session, payload.task_id)
    _validate_plan(
        payload.week_start_date,
        payload.week_end_date,
        payload.target_description,
    )
    await _ensure_unique_week(
        session,
        payload.task_id,
        payload.week_start_date,
    )

    plan = WeeklyTaskPlan(
        task_id=payload.task_id,
        week_start_date=payload.week_start_date,
        week_end_date=payload.week_end_date,
        target_description=payload.target_description.strip(),
        target_completion_percentage=(
            payload.target_completion_percentage
        ),
    )

    session.add(plan)
    await session.commit()
    await session.refresh(plan)

    return await get_plan(session, plan.id)


async def update_plan(
    session: AsyncSession,
    plan_id: int,
    payload: WeeklyPlanUpdate,
) -> WeeklyPlanRead:
    plan = await session.get(WeeklyTaskPlan, plan_id)

    if plan is None:
        raise NotFoundError("Haftalık plan bulunamadı.")

    fields = payload.model_dump(exclude_unset=True)

    if "task_id" in fields and fields["task_id"] is not None:
        await _ensure_task(session, fields["task_id"])
        plan.task_id = fields["task_id"]

    if "week_start_date" in fields and fields["week_start_date"] is not None:
        plan.week_start_date = fields["week_start_date"]

    if "week_end_date" in fields and fields["week_end_date"] is not None:
        plan.week_end_date = fields["week_end_date"]

    if (
        "target_description" in fields
        and fields["target_description"] is not None
    ):
        plan.target_description = fields["target_description"].strip()

    if "target_completion_percentage" in fields:
        plan.target_completion_percentage = fields[
            "target_completion_percentage"
        ]

    _validate_plan(
        plan.week_start_date,
        plan.week_end_date,
        plan.target_description,
    )
    await _ensure_unique_week(
        session,
        plan.task_id,
        plan.week_start_date,
        exclude_plan_id=plan.id,
    )

    await session.commit()
    await session.refresh(plan)

    return await get_plan(session, plan.id)
