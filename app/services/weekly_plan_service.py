import hashlib
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import (
    Project,
    Task,
    TaskAssignment,
    TaskUpdate,
    WeeklyPlanGeneration,
    WeeklyTaskPlan,
)
from app.schemas.ai_weekly_plan import AIWeeklyPlanResult
from app.schemas.common import Page
from app.schemas.weekly_plan import (
    AIPlanGenerateRequest,
    AIPlanGenerateResponse,
    WeeklyPlanCreate,
    WeeklyPlanRead,
    WeeklyPlanSource,
    WeeklyPlanStatus,
    WeeklyPlanUpdate,
)
from app.services.ai_service import (
    DEFAULT_GEMINI_MODEL,
    AIPlanGenerationError,
    generate_weekly_plan_drafts,
)
from app.services.exceptions import (
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)


logger = logging.getLogger("worktrack.weekly_plans")

MAX_AI_WEEKS_PER_TASK = 104

EDITABLE_STATUSES = {WeeklyPlanStatus.DRAFT.value}


class AIPlanOutputError(RuntimeError):
    """The AI answered, but its output failed backend validation."""


def _log_pydantic_validation_error(
    exc: PydanticValidationError,
) -> None:
    """Log Pydantic schema diagnostics without leaking their inputs.

    Only ``loc``, ``type`` and ``msg`` are emitted. Pydantic also exposes
    the rejected ``input`` value (which can contain the administrator's
    instructions, task descriptions or other request data) and a docs
    URL; neither is logged.
    """

    details = [
        {
            "loc": ".".join(str(part) for part in error.get("loc", ())),
            "type": error.get("type"),
            "msg": error.get("msg"),
        }
        for error in exc.errors(include_url=False)
    ]

    logger.warning(
        "AI weekly plan Pydantic validation failed: %s",
        details,
    )


def _base_plan_query():
    return (
        select(
            WeeklyTaskPlan,
            Task.title.label("task_title"),
            Project.id.label("project_id"),
            Project.name.label("project_name"),
            WeeklyPlanGeneration.request_id.label("generation_request_id"),
        )
        .join(Task, Task.id == WeeklyTaskPlan.task_id)
        .join(Project, Project.id == Task.project_id)
        .outerjoin(
            WeeklyPlanGeneration,
            WeeklyPlanGeneration.id == WeeklyTaskPlan.generation_id,
        )
    )


def _serialize_plan(
    plan: WeeklyTaskPlan,
    task_title: str,
    project_id: int,
    project_name: str,
    generation_request_id: str | None = None,
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
        status=plan.status,
        source=plan.source,
        generation_id=plan.generation_id,
        generation_request_id=generation_request_id,
        ai_rationale=plan.ai_rationale,
        ai_assumptions=plan.ai_assumptions,
        ai_warnings=plan.ai_warnings,
        approved_at=plan.approved_at,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def _validate_plan(
    week_start_date: date,
    week_end_date: date,
    target_description: str,
) -> None:
    if week_end_date < week_start_date:
        raise ValidationError(
            "Hafta bitiş tarihi, hafta başlangıç tarihinden önce olamaz."
        )

    if not target_description.strip():
        raise ValidationError("Haftalık hedef açıklaması boş olamaz.")


def _week_windows(
    planned_start_date: date,
    planned_due_date: date,
) -> list[tuple[date, date]]:
    """Return Monday-based planning weeks clipped to the task dates."""

    if planned_due_date < planned_start_date:
        raise ValidationError(
            "Görevin planlanan bitiş tarihi başlangıçtan önce olamaz."
        )

    first_monday = planned_start_date - timedelta(
        days=planned_start_date.weekday()
    )
    windows: list[tuple[date, date]] = []
    cursor = first_monday

    while cursor <= planned_due_date:
        window_start = max(cursor, planned_start_date)
        window_end = min(cursor + timedelta(days=6), planned_due_date)
        windows.append((window_start, window_end))

        if len(windows) > MAX_AI_WEEKS_PER_TASK:
            raise ValidationError(
                "Görev aralığı AI planı için çok uzun. "
                f"En fazla {MAX_AI_WEEKS_PER_TASK} hafta destekleniyor."
            )

        cursor += timedelta(days=7)

    return windows


async def _ensure_task(
    session: AsyncSession,
    task_id: int,
) -> None:
    exists = await session.scalar(
        select(Task.id).where(Task.id == task_id)
    )
    if exists is None:
        raise NotFoundError("Görev bulunamadı.")


async def _ensure_manual_week_is_free(
    session: AsyncSession,
    task_id: int,
    week_start_date: date,
    exclude_plan_id: int | None = None,
) -> None:
    stmt = select(WeeklyTaskPlan.id).where(
        WeeklyTaskPlan.task_id == task_id,
        WeeklyTaskPlan.week_start_date == week_start_date,
        WeeklyTaskPlan.status.notin_(
            [
                WeeklyPlanStatus.REJECTED.value,
                WeeklyPlanStatus.SUPERSEDED.value,
            ]
        ),
    )

    if exclude_plan_id is not None:
        stmt = stmt.where(WeeklyTaskPlan.id != exclude_plan_id)

    exists = await session.scalar(stmt)

    if exists is not None:
        raise ConflictError(
            "Bu görev için seçilen haftada zaten aktif bir plan var. "
            "Mevcut planı düzenleyin veya AI ile yeni bir taslak oluşturun."
        )


async def _ensure_cumulative_order(
    session: AsyncSession,
    plan: WeeklyTaskPlan,
) -> None:
    if plan.target_completion_percentage is None:
        return

    rows = (
        await session.execute(
            select(WeeklyTaskPlan).where(
                WeeklyTaskPlan.task_id == plan.task_id,
                WeeklyTaskPlan.id != plan.id,
                WeeklyTaskPlan.status == WeeklyPlanStatus.APPROVED.value,
            )
        )
    ).scalars().all()

    for other in rows:
        if other.target_completion_percentage is None:
            continue

        if (
            other.week_start_date < plan.week_start_date
            and other.target_completion_percentage
            > plan.target_completion_percentage
        ):
            raise ConflictError(
                "Kümülatif ilerleme geriye gidemez. Daha önceki haftanın "
                "onaylı hedefi bu plandan yüksek."
            )

        if (
            other.week_start_date > plan.week_start_date
            and other.target_completion_percentage
            < plan.target_completion_percentage
        ):
            raise ConflictError(
                "Kümülatif ilerleme geriye gidemez. Daha sonraki haftanın "
                "onaylı hedefi bu plandan düşük."
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

    (
        plan,
        task_title,
        project_id,
        project_name,
        generation_request_id,
    ) = row
    return _serialize_plan(
        plan,
        task_title,
        project_id,
        project_name,
        generation_request_id,
    )


async def list_plans(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    task_id: int | None = None,
    project_id: int | None = None,
    week_start_date: date | None = None,
    status: WeeklyPlanStatus | None = None,
    source: WeeklyPlanSource | None = None,
    generation_id: int | None = None,
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

    if status is not None:
        filters.append(WeeklyTaskPlan.status == status.value)

    if source is not None:
        filters.append(WeeklyTaskPlan.source == source.value)

    if generation_id is not None:
        filters.append(WeeklyTaskPlan.generation_id == generation_id)

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
        _serialize_plan(
            plan,
            task_title,
            project_id,
            project_name,
            generation_request_id,
        )
        for (
            plan,
            task_title,
            project_id,
            project_name,
            generation_request_id,
        ) in rows
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
    await _ensure_manual_week_is_free(
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
        status=WeeklyPlanStatus.DRAFT.value,
        source=WeeklyPlanSource.MANUAL.value,
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

    if plan.status not in EDITABLE_STATUSES:
        raise ConflictError(
            "Yalnızca taslak planlar düzenlenebilir. Onaylanmış bir planı "
            "değiştirmek için yeni bir taslak oluşturup onaylayın."
        )

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

    if plan.source == WeeklyPlanSource.MANUAL.value:
        await _ensure_manual_week_is_free(
            session,
            plan.task_id,
            plan.week_start_date,
            exclude_plan_id=plan.id,
        )

    await session.commit()
    await session.refresh(plan)

    return await get_plan(session, plan.id)


async def approve_plan(
    session: AsyncSession,
    plan_id: int,
    *,
    replace_existing: bool = False,
) -> WeeklyPlanRead:
    plan = await session.get(WeeklyTaskPlan, plan_id)

    if plan is None:
        raise NotFoundError("Haftalık plan bulunamadı.")

    if plan.status == WeeklyPlanStatus.APPROVED.value:
        return await get_plan(session, plan.id)

    if plan.status != WeeklyPlanStatus.DRAFT.value:
        raise ConflictError(
            "Yalnızca taslak planlar onaylanabilir."
        )

    conflict = await session.scalar(
        select(WeeklyTaskPlan).where(
            WeeklyTaskPlan.task_id == plan.task_id,
            WeeklyTaskPlan.week_start_date == plan.week_start_date,
            WeeklyTaskPlan.status == WeeklyPlanStatus.APPROVED.value,
            WeeklyTaskPlan.id != plan.id,
        )
    )

    if conflict is not None:
        if not replace_existing:
            raise ConflictError(
                "Bu görev ve hafta için zaten onaylanmış bir plan var. "
                "Yeni planı onaylarsanız eski plan 'Eski Plan' olarak "
                "saklanacaktır. Devam etmek için onayı yineleyin."
            )

        conflict.status = WeeklyPlanStatus.SUPERSEDED.value

    await _ensure_cumulative_order(session, plan)

    plan.status = WeeklyPlanStatus.APPROVED.value
    plan.approved_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(plan)

    return await get_plan(session, plan.id)


async def reject_plan(
    session: AsyncSession,
    plan_id: int,
) -> WeeklyPlanRead:
    plan = await session.get(WeeklyTaskPlan, plan_id)

    if plan is None:
        raise NotFoundError("Haftalık plan bulunamadı.")

    if plan.status == WeeklyPlanStatus.REJECTED.value:
        return await get_plan(session, plan.id)

    if plan.status != WeeklyPlanStatus.DRAFT.value:
        raise ConflictError(
            "Yalnızca taslak planlar reddedilebilir."
        )

    plan.status = WeeklyPlanStatus.REJECTED.value
    await session.commit()
    await session.refresh(plan)

    return await get_plan(session, plan.id)


async def delete_plan(
    session: AsyncSession,
    plan_id: int,
) -> None:
    """Delete a weekly plan in any lifecycle state.

    Reports referencing the plan are historical records; they block the
    deletion and must be removed explicitly by the administrator first.
    Approved/superseded plans are deletable because the administrator owns
    the planning data, but no report history is ever removed implicitly.
    """

    plan = await session.get(WeeklyTaskPlan, plan_id)

    if plan is None:
        raise NotFoundError("Haftalık plan bulunamadı.")

    update_count = int(
        (
            await session.execute(
                select(func.count(TaskUpdate.id)).where(
                    TaskUpdate.weekly_plan_id == plan.id
                )
            )
        ).scalar_one()
    )

    if update_count > 0:
        raise ConflictError(
            f"Bu plana bağlı {update_count} iş raporu bulunuyor. "
            "Rapor geçmişinin korunması için plan silinemez. "
            "Lütfen önce ilgili raporları silin."
        )

    await session.delete(plan)
    await session.commit()


async def _load_generation_tasks(
    session: AsyncSession,
    task_ids: list[int],
) -> list[tuple[Task, Project]]:
    unique_ids = list(dict.fromkeys(task_ids))

    rows = (
        await session.execute(
            select(Task, Project)
            .join(Project, Project.id == Task.project_id)
            .where(Task.id.in_(unique_ids))
            .options(
                selectinload(Task.assignments).selectinload(
                    TaskAssignment.employee
                )
            )
        )
    ).all()

    by_id = {task.id: (task, project) for task, project in rows}

    if set(by_id) != set(unique_ids):
        raise NotFoundError(
            "Seçilen görevlerden bazıları bulunamadı."
        )

    return [by_id[task_id] for task_id in unique_ids]


async def _load_existing_plans(
    session: AsyncSession,
    task_ids: list[int],
) -> dict[int, list[WeeklyTaskPlan]]:
    rows = (
        await session.execute(
            select(WeeklyTaskPlan)
            .where(
                WeeklyTaskPlan.task_id.in_(task_ids),
                WeeklyTaskPlan.status.in_(
                    [
                        WeeklyPlanStatus.DRAFT.value,
                        WeeklyPlanStatus.APPROVED.value,
                    ]
                ),
            )
            .order_by(
                WeeklyTaskPlan.task_id,
                WeeklyTaskPlan.week_start_date,
            )
        )
    ).scalars().all()

    result: dict[int, list[WeeklyTaskPlan]] = {}

    for plan in rows:
        result.setdefault(plan.task_id, []).append(plan)

    return result


def _serialize_task_context(
    task: Task,
    project: Project,
    plans: list[WeeklyTaskPlan],
    windows: list[tuple[date, date]],
) -> dict:
    employees = sorted(
        (
            {
                "full_name": assignment.employee.full_name,
                "role": assignment.employee.role,
                "is_active": assignment.employee.is_active,
            }
            for assignment in task.assignments
        ),
        key=lambda employee: employee["full_name"].casefold(),
    )

    return {
        "task_id": task.id,
        "title": task.title,
        "description": task.description,
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "location": project.location,
            "expected_completion_date": (
                project.expected_completion_date.isoformat()
                if project.expected_completion_date
                else None
            ),
        },
        "planned_start_date": task.planned_start_date.isoformat(),
        "planned_due_date": task.planned_due_date.isoformat(),
        "assigned_employees": employees,
        "existing_plans": [
            {
                "week_start_date": plan.week_start_date.isoformat(),
                "week_end_date": plan.week_end_date.isoformat(),
                "target_description": plan.target_description,
                "target_completion_percentage": (
                    plan.target_completion_percentage
                ),
                "status": plan.status,
                "source": plan.source,
            }
            for plan in plans
        ],
        "week_windows": [
            {
                "week_start_date": start.isoformat(),
                "week_end_date": end.isoformat(),
            }
            for start, end in windows
        ],
    }


async def _build_ai_context(
    session: AsyncSession,
    task_ids: list[int],
    extra_instructions: str | None,
) -> tuple[dict, dict[int, tuple[date, date]]]:
    task_rows = await _load_generation_tasks(session, task_ids)
    existing_plans = await _load_existing_plans(
        session,
        [task.id for task, _ in task_rows],
    )

    missing_dates = [
        task.title
        for task, _ in task_rows
        if task.planned_start_date is None or task.planned_due_date is None
    ]

    if missing_dates:
        raise ValidationError(
            "AI planı için planlanan başlangıç ve bitiş tarihleri "
            "eksik olan görevler var: "
            + ", ".join(missing_dates)
            + ". Önce görev tarihlerini tamamlayın."
        )

    windows_by_task: dict[int, list[tuple[date, date]]] = {}
    task_contexts = []

    for task, project in task_rows:
        windows = _week_windows(
            task.planned_start_date,
            task.planned_due_date,
        )
        windows_by_task[task.id] = windows
        task_contexts.append(
            _serialize_task_context(
                task,
                project,
                existing_plans.get(task.id, []),
                windows,
            )
        )

    context = {
        "today": date.today().isoformat(),
        "week_definition": (
            "Planning weeks start on Monday and cover seven days, "
            "clipped to the task's real planned start and due dates."
        ),
        "extra_instructions": (
            extra_instructions.strip()
            if extra_instructions and extra_instructions.strip()
            else None
        ),
        "tasks": task_contexts,
    }

    return context, windows_by_task


def _request_fingerprint(
    task_ids: list[int],
    extra_instructions: str | None,
) -> str:
    raw = json.dumps(
        {
            "task_ids": sorted(task_ids),
            "extra_instructions": (
                extra_instructions.strip()
                if extra_instructions and extra_instructions.strip()
                else None
            ),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _format_notes(items: list[str], limit: int = 20) -> str | None:
    cleaned = [
        item.strip()[:1000]
        for item in items
        if item and item.strip()
    ][:limit]

    if not cleaned:
        return None

    return "\n".join(f"- {item}" for item in cleaned)


def _validate_ai_output(
    result: AIWeeklyPlanResult,
    windows_by_task: dict[int, list[tuple[date, date]]],
) -> None:
    seen: set[int] = set()

    for group in result.tasks:
        if group.task_id in seen:
            raise AIPlanOutputError(
                "AI returned the same task more than once."
            )
        seen.add(group.task_id)

        if group.task_id not in windows_by_task:
            raise AIPlanOutputError(
                "AI returned an unknown task ID."
            )

        expected_windows = windows_by_task[group.task_id]

        if len(group.weeks) != len(expected_windows):
            raise AIPlanOutputError(
                "AI returned an invalid number of weeks."
            )

        previous_percentage = -1

        for week, expected in zip(group.weeks, expected_windows):
            try:
                week_start = date.fromisoformat(week.week_start_date)
                week_end = date.fromisoformat(week.week_end_date)
            except ValueError as exc:
                raise AIPlanOutputError(
                    "AI returned an invalid date."
                ) from exc

            if (week_start, week_end) != expected:
                raise AIPlanOutputError(
                    "AI week dates do not match the calculated windows."
                )

            if not week.target_description.strip():
                raise AIPlanOutputError(
                    "AI returned an empty weekly target."
                )

            percentage = week.target_completion_percentage

            if percentage < 0 or percentage > 100:
                raise AIPlanOutputError(
                    "AI returned a percentage outside 0-100."
                )

            if percentage < previous_percentage:
                raise AIPlanOutputError(
                    "AI returned a decreasing cumulative percentage."
                )

            previous_percentage = percentage

    if seen != set(windows_by_task):
        raise AIPlanOutputError(
            "AI did not return a plan for every requested task."
        )


async def _get_generation_by_request_id(
    session: AsyncSession,
    request_id: str,
) -> WeeklyPlanGeneration | None:
    return await session.scalar(
        select(WeeklyPlanGeneration).where(
            WeeklyPlanGeneration.request_id == request_id
        )
    )


async def _generation_plans(
    session: AsyncSession,
    generation_id: int,
) -> list[WeeklyPlanRead]:
    rows = (
        await session.execute(
            _base_plan_query()
            .where(WeeklyTaskPlan.generation_id == generation_id)
            .order_by(
                WeeklyTaskPlan.task_id,
                WeeklyTaskPlan.week_start_date,
            )
        )
    ).all()

    return [
        _serialize_plan(
            plan,
            task_title,
            project_id,
            project_name,
            generation_request_id,
        )
        for (
            plan,
            task_title,
            project_id,
            project_name,
            generation_request_id,
        ) in rows
    ]


async def _generation_response(
    session: AsyncSession,
    generation: WeeklyPlanGeneration,
    task_ids: list[int] | None = None,
) -> AIPlanGenerateResponse:
    plans = await _generation_plans(session, generation.id)

    return AIPlanGenerateResponse(
        generation_id=generation.id,
        request_id=generation.request_id,
        plan_count=len(plans),
        tasks=task_ids or sorted({plan.task_id for plan in plans}),
        plans=plans,
    )


async def _mark_generation_failed(
    session: AsyncSession,
    generation_id: int,
    message: str,
) -> None:
    try:
        await session.rollback()
        generation = await session.get(
            WeeklyPlanGeneration,
            generation_id,
        )

        if generation is None:
            return

        generation.status = "failed"
        generation.error_message = message
        await session.commit()
    except Exception:
        logger.exception("Could not mark AI generation as failed.")


async def _reserve_generation(
    session: AsyncSession,
    request_id: str,
    fingerprint: str,
    extra_instructions: str | None,
    model: str,
) -> tuple[WeeklyPlanGeneration, bool]:
    """Return (generation, already_completed)."""

    existing = await _get_generation_by_request_id(
        session,
        request_id,
    )

    if existing is not None:
        if (
            existing.request_fingerprint is not None
            and existing.request_fingerprint != fingerprint
        ):
            raise ConflictError(
                "Bu istek kimliği farklı bir AI planı isteği için "
                "kullanılmış. Lütfen yeni bir istek başlatın."
            )

        if existing.status == "completed":
            return existing, True

        if existing.status == "pending":
            raise ConflictError(
                "Bu AI planı isteği hâlâ işleniyor. Lütfen bekleyin."
            )

        existing.status = "pending"
        existing.error_message = None
        existing.extra_instructions = extra_instructions
        existing.model = model
        existing.request_fingerprint = fingerprint
        await session.commit()
        return existing, False

    generation = WeeklyPlanGeneration(
        request_id=request_id,
        request_fingerprint=fingerprint,
        model=model,
        extra_instructions=extra_instructions,
        status="pending",
    )

    session.add(generation)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await _get_generation_by_request_id(
            session,
            request_id,
        )

        if existing is None:
            raise ConflictError(
                "AI planı isteği kaydedilemedi. Lütfen tekrar deneyin."
            )

        if (
            existing.request_fingerprint is not None
            and existing.request_fingerprint != fingerprint
        ):
            raise ConflictError(
                "Bu istek kimliği farklı bir AI planı isteği için "
                "kullanılmış."
            )

        if existing.status == "completed":
            return existing, True

        if existing.status == "pending":
            raise ConflictError(
                "Bu AI planı isteği hâlâ işleniyor. Lütfen bekleyin."
            )

        existing.status = "pending"
        existing.error_message = None
        existing.extra_instructions = extra_instructions
        existing.model = model
        await session.commit()
        return existing, False

    return generation, False


async def generate_ai_plans(
    session: AsyncSession,
    payload: AIPlanGenerateRequest,
) -> AIPlanGenerateResponse:
    task_ids = list(dict.fromkeys(payload.task_ids))
    extra_instructions = payload.extra_instructions

    context, windows_by_task = await _build_ai_context(
        session,
        task_ids,
        extra_instructions,
    )

    request_id = payload.request_id or uuid4().hex
    fingerprint = _request_fingerprint(task_ids, extra_instructions)
    model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)

    generation, already_completed = await _reserve_generation(
        session,
        request_id,
        fingerprint,
        extra_instructions.strip() if extra_instructions else None,
        model,
    )

    if already_completed:
        return await _generation_response(
            session,
            generation,
            task_ids,
        )

    try:
        generated = await generate_weekly_plan_drafts(context)
        _validate_ai_output(generated.result, windows_by_task)
    except AIPlanGenerationError as exc:
        safe_message = (
            "AI planı geçerli biçimde oluşturulamadı. "
            "Lütfen tekrar deneyin veya talimatları netleştirin."
        )
        await _mark_generation_failed(
            session,
            generation.id,
            safe_message,
        )
        logger.warning(
            "AI weekly plan generation failed: %s",
            type(exc).__name__,
        )
        raise ServiceUnavailableError(
            "AI planlama servisi şu anda yanıt veremedi. "
            "Lütfen daha sonra tekrar deneyin."
        ) from exc
    except AIPlanOutputError as exc:
        safe_message = (
            "AI çıktısı doğrulanamadı: tarih, hafta veya yüzde "
            "değerleri geçersiz."
        )
        await _mark_generation_failed(
            session,
            generation.id,
            safe_message,
        )
        logger.warning(
            "AI weekly plan output validation failed: %s",
            str(exc),
        )
        raise ServiceUnavailableError(
            "AI geçerli bir haftalık plan üretemedi. "
            "Lütfen tekrar deneyin veya talimatları netleştirin."
        ) from exc
    except PydanticValidationError as exc:
        # Raised while the Gemini SDK builds the request (for example when
        # a JSON Schema keyword is not supported by the SDK's Schema
        # model), so no AI request was sent and no prompt data is logged.
        await _mark_generation_failed(
            session,
            generation.id,
            "AI planlama isteği doğrulanamadı.",
        )
        _log_pydantic_validation_error(exc)
        raise ServiceUnavailableError(
            "AI planlama isteği doğrulanamadı. "
            "Lütfen daha sonra tekrar deneyin."
        ) from exc
    except Exception as exc:
        safe_message = "AI planlama servisi yanıt veremedi."
        await _mark_generation_failed(
            session,
            generation.id,
            safe_message,
        )
        logger.exception("Unexpected AI weekly plan error.")
        raise ServiceUnavailableError(
            "AI planlama servisi şu anda yanıt veremedi. "
            "Lütfen daha sonra tekrar deneyin."
        ) from exc

    groups = {group.task_id: group for group in generated.result.tasks}

    for task_id in task_ids:
        group = groups[task_id]

        for week in group.weeks:
            week_rationale = (
                week.rationale.strip()
                if week.rationale and week.rationale.strip()
                else None
            )
            session.add(
                WeeklyTaskPlan(
                    task_id=task_id,
                    week_start_date=date.fromisoformat(
                        week.week_start_date
                    ),
                    week_end_date=date.fromisoformat(
                        week.week_end_date
                    ),
                    target_description=week.target_description.strip(),
                    target_completion_percentage=(
                        week.target_completion_percentage
                    ),
                    status=WeeklyPlanStatus.DRAFT.value,
                    source=WeeklyPlanSource.AI.value,
                    generation_id=generation.id,
                    ai_rationale=week_rationale,
                    ai_assumptions=_format_notes(group.assumptions),
                    ai_warnings=_format_notes(group.warnings),
                )
            )

    generation.status = "completed"
    generation.model = generated.model
    generation.completed_at = datetime.now(timezone.utc)
    generation.error_message = None

    try:
        await session.commit()
    except Exception as exc:
        await _mark_generation_failed(
            session,
            generation.id,
            "AI taslakları kaydedilemedi.",
        )
        logger.exception("Could not persist AI weekly plan drafts.")
        raise ServiceUnavailableError(
            "AI taslakları kaydedilemedi. Lütfen tekrar deneyin."
        ) from exc

    return await _generation_response(
        session,
        generation,
        task_ids,
    )
