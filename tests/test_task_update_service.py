from datetime import date

import pytest
from sqlalchemy import event, func, select

from app.database.models import TaskUpdate, WeeklyTaskPlan
from app.schemas.work_update import WorkStatus, WorkUpdate
from app.services import employee_work_service
from app.services.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from tests.test_employee_work_reports import (
    TODAY,
    seed_plan,
    seed_task,
)
from tests.test_employees_tasks import seed_employee


TELEGRAM_USER_ID = 8001
NEXT_WEEK_END = date(2026, 11, 22)
ETA_DATE = date(2026, 11, 18)  # Wednesday


def make_draft(**overrides) -> WorkUpdate:
    data = {
        "task_reference_text": "Elektrik tesisatı",
        "status": "in_progress",
        "completion_percentage": 70,
        "blocker": None,
        "delay_reason": None,
        "next_step": "Pano bağlantılarını tamamla",
        "reported_eta_text": "cuma gününe kadar",
        "summary": "İşin %70'i tamamlandı.",
    }
    data.update(overrides)
    return WorkUpdate.model_validate(data)


async def seed_worker(
    session,
    *,
    telegram_user_id: int = TELEGRAM_USER_ID,
    is_active: bool = True,
) -> int:
    return await seed_employee(
        session,
        "Rapor Çalışanı",
        is_active=is_active,
        telegram_user_id=telegram_user_id,
    )


async def seed_assigned_task(session, employee_id: int) -> int:
    _, task_id = await seed_task(
        session,
        title="Elektrik tesisatı",
        project_name="Rapor Projesi",
        employee_ids=(employee_id,),
    )
    return task_id


async def create_update(
    session,
    *,
    telegram_user_id: int = TELEGRAM_USER_ID,
    task_id: int,
    weekly_plan_id: int | None = None,
    message_id: int = 100,
    draft: WorkUpdate | None = None,
    reported_eta_date: date | None = ETA_DATE,
    ai_model: str | None = "gemini-test-model",
):
    return await employee_work_service.create_task_update(
        session,
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_user_id,
        telegram_message_id=message_id,
        task_id=task_id,
        weekly_plan_id=weekly_plan_id,
        original_message="Bu hafta işin %70'ini tamamladık.",
        draft=draft or make_draft(),
        reported_eta_date=reported_eta_date,
        ai_model=ai_model,
        today=TODAY,
    )


async def count_updates(session) -> int:
    return int(
        (
            await session.execute(
                select(func.count(TaskUpdate.id))
            )
        ).scalar_one()
    )


async def test_active_assigned_employee_can_create_task_update(session):
    employee_id = await seed_worker(session)
    task_id = await seed_assigned_task(session, employee_id)
    plan_id = await seed_plan(session, task_id, TODAY, NEXT_WEEK_END)

    update = await create_update(
        session,
        task_id=task_id,
        weekly_plan_id=plan_id,
    )
    await session.commit()
    await session.refresh(update)

    assert update.id is not None
    assert update.task_id == task_id
    assert update.employee_id == employee_id
    assert update.weekly_plan_id == plan_id
    assert update.telegram_user_id == TELEGRAM_USER_ID
    assert update.telegram_chat_id == TELEGRAM_USER_ID
    assert update.telegram_message_id == 100
    assert update.original_message == (
        "Bu hafta işin %70'ini tamamladık."
    )
    assert update.sync_status == "not_synced"
    assert await count_updates(session) == 1


async def test_all_ai_fields_are_persisted(session):
    employee_id = await seed_worker(session)
    task_id = await seed_assigned_task(session, employee_id)

    draft = make_draft(
        task_reference_text="Ana pano bağlantıları",
        status=WorkStatus.BLOCKED,
        completion_percentage=65,
        blocker="Kablo temini",
        delay_reason="Tedarik gecikmesi",
        next_step="Kablolar gelince devam et",
        reported_eta_text="gelecek hafta",
        summary="Pano bağlantıları kablo bekliyor.",
    )

    update = await create_update(session, task_id=task_id, draft=draft)
    await session.commit()
    await session.refresh(update)

    assert update.task_reference_text == "Ana pano bağlantıları"
    assert update.status == "blocked"
    assert update.completion_percentage == 65
    assert update.blocker == "Kablo temini"
    assert update.delay_reason == "Tedarik gecikmesi"
    assert update.next_step == "Kablolar gelince devam et"
    assert update.reported_eta_text == "gelecek hafta"
    assert update.summary == "Pano bağlantıları kablo bekliyor."
    assert update.ai_model == "gemini-test-model"


async def test_eta_text_and_normalized_date_are_persisted(session):
    employee_id = await seed_worker(session)
    task_id = await seed_assigned_task(session, employee_id)

    update = await create_update(session, task_id=task_id)
    await session.commit()
    await session.refresh(update)

    assert update.reported_eta_text == "cuma gününe kadar"
    assert update.reported_eta_date == ETA_DATE


async def test_employee_approval_fields_are_recorded(session):
    employee_id = await seed_worker(session)
    task_id = await seed_assigned_task(session, employee_id)

    update = await create_update(session, task_id=task_id)
    await session.commit()
    await session.refresh(update)

    assert update.review_status == "approved"
    assert update.reviewed_by_employee_id == employee_id
    assert update.reviewed_at is not None
    assert update.reviewed_at.tzinfo is not None


async def test_inactive_employee_cannot_create_update(session):
    employee_id = await seed_worker(session, is_active=False)
    task_id = await seed_assigned_task(session, employee_id)

    with pytest.raises(NotFoundError):
        await create_update(session, task_id=task_id)

    assert await count_updates(session) == 0


async def test_unknown_telegram_user_cannot_create_update(session):
    employee_id = await seed_worker(session)
    task_id = await seed_assigned_task(session, employee_id)

    with pytest.raises(NotFoundError):
        await create_update(
            session,
            telegram_user_id=999999,
            task_id=task_id,
        )

    assert await count_updates(session) == 0


async def test_unassigned_task_is_rejected(session):
    other_employee_id = await seed_worker(
        session,
        telegram_user_id=8100,
    )
    employee_id = await seed_worker(
        session,
        telegram_user_id=8101,
    )
    task_id = await seed_assigned_task(session, other_employee_id)

    with pytest.raises(NotFoundError):
        await create_update(
            session,
            telegram_user_id=8101,
            task_id=task_id,
        )

    assert await count_updates(session) == 0
    assert employee_id != other_employee_id


async def test_unknown_task_is_rejected(session):
    await seed_worker(session)

    with pytest.raises(NotFoundError):
        await create_update(session, task_id=999999)

    assert await count_updates(session) == 0


async def test_plan_of_another_task_is_rejected(session):
    employee_id = await seed_worker(session)
    task_id = await seed_assigned_task(session, employee_id)

    _, other_task_id = await seed_task(
        session,
        title="Diğer görev",
        project_name="Diğer Proje",
        employee_ids=(employee_id,),
    )
    other_plan_id = await seed_plan(
        session,
        other_task_id,
        TODAY,
        NEXT_WEEK_END,
    )

    with pytest.raises(ValidationError):
        await create_update(
            session,
            task_id=task_id,
            weekly_plan_id=other_plan_id,
        )

    assert await count_updates(session) == 0


@pytest.mark.parametrize(
    "status",
    ["draft", "rejected", "superseded"],
)
async def test_non_approved_plan_is_rejected(session, status):
    employee_id = await seed_worker(session)
    task_id = await seed_assigned_task(session, employee_id)
    plan_id = await seed_plan(
        session,
        task_id,
        TODAY,
        NEXT_WEEK_END,
        status=status,
    )

    with pytest.raises(ValidationError):
        await create_update(
            session,
            task_id=task_id,
            weekly_plan_id=plan_id,
        )

    assert await count_updates(session) == 0


async def test_plan_outside_today_is_rejected(session):
    employee_id = await seed_worker(session)
    task_id = await seed_assigned_task(session, employee_id)
    plan_id = await seed_plan(
        session,
        task_id,
        date(2026, 11, 23),
        date(2026, 11, 29),
    )

    with pytest.raises(ValidationError):
        await create_update(
            session,
            task_id=task_id,
            weekly_plan_id=plan_id,
        )

    assert await count_updates(session) == 0


async def test_update_without_plan_is_allowed(session):
    employee_id = await seed_worker(session)
    task_id = await seed_assigned_task(session, employee_id)

    update = await create_update(session, task_id=task_id)
    await session.commit()
    await session.refresh(update)

    assert update.weekly_plan_id is None
    assert update.task_id == task_id


async def test_conflicting_plans_are_not_chosen_automatically(session):
    employee_id = await seed_worker(session)
    task_id = await seed_assigned_task(session, employee_id)
    await seed_plan(
        session,
        task_id,
        date(2026, 11, 9),
        TODAY,
        description="Eski hedef",
    )
    await seed_plan(
        session,
        task_id,
        TODAY,
        NEXT_WEEK_END,
        description="Yeni hedef",
    )

    # The caller could not resolve a single plan and passes None.
    update = await create_update(session, task_id=task_id)
    await session.commit()
    await session.refresh(update)

    assert update.weekly_plan_id is None


async def test_duplicate_telegram_message_is_rejected(session):
    employee_id = await seed_worker(session)
    task_id = await seed_assigned_task(session, employee_id)

    await create_update(session, task_id=task_id, message_id=200)
    await session.commit()

    with pytest.raises(ConflictError):
        await create_update(session, task_id=task_id, message_id=200)

    assert await count_updates(session) == 1


async def test_two_different_messages_create_two_updates(session):
    employee_id = await seed_worker(session)
    task_id = await seed_assigned_task(session, employee_id)

    await create_update(session, task_id=task_id, message_id=201)
    await session.commit()
    await create_update(session, task_id=task_id, message_id=202)
    await session.commit()

    assert await count_updates(session) == 2


async def test_plan_is_unchanged_after_report(session):
    employee_id = await seed_worker(session)
    task_id = await seed_assigned_task(session, employee_id)
    plan_id = await seed_plan(
        session,
        task_id,
        TODAY,
        NEXT_WEEK_END,
        description="Değişmemesi gereken hedef",
        percentage=55,
    )

    plan = await session.get(WeeklyTaskPlan, plan_id)
    before = {
        "target_description": plan.target_description,
        "target_completion_percentage": (
            plan.target_completion_percentage
        ),
        "status": plan.status,
        "week_start_date": plan.week_start_date,
        "week_end_date": plan.week_end_date,
        "approved_at": plan.approved_at,
        "updated_at": plan.updated_at,
    }

    await create_update(
        session,
        task_id=task_id,
        weekly_plan_id=plan_id,
    )
    await session.commit()
    await session.refresh(plan)

    after = {
        "target_description": plan.target_description,
        "target_completion_percentage": (
            plan.target_completion_percentage
        ),
        "status": plan.status,
        "week_start_date": plan.week_start_date,
        "week_end_date": plan.week_end_date,
        "approved_at": plan.approved_at,
        "updated_at": plan.updated_at,
    }

    assert after == before


async def test_generated_weekday_column_is_not_written_by_app(session):
    employee_id = await seed_worker(session)
    task_id = await seed_assigned_task(session, employee_id)

    statements: list[str] = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        if "INSERT INTO task_updates" in statement:
            statements.append(statement)

    engine = session.bind.sync_engine
    event.listen(engine, "before_cursor_execute", capture)

    try:
        update = await create_update(
            session,
            task_id=task_id,
            reported_eta_date=ETA_DATE,
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert statements, "expected an INSERT into task_updates"

    # Generated columns must not appear in the inserted column list; the
    # database derives the Turkish weekday from reported_eta_date.
    inserted_columns = statements[0].split("RETURNING")[0]
    assert "reported_eta_weekday" not in inserted_columns

    await session.commit()
    await session.refresh(update)

    assert update.reported_eta_weekday == "çarşamba"


async def test_task_id_is_always_present_on_new_updates(session):
    employee_id = await seed_worker(session)
    task_id = await seed_assigned_task(session, employee_id)

    update = await create_update(session, task_id=task_id)
    await session.commit()
    await session.refresh(update)

    assert update.task_id == task_id
    assert update.task_id is not None

    missing = await session.scalar(
        select(func.count(TaskUpdate.id)).where(
            TaskUpdate.task_id.is_(None)
        )
    )
    assert missing == 0


async def test_database_constraint_blocks_concurrent_duplicate(
    session,
    monkeypatch,
):
    employee_id = await seed_worker(session)
    task_id = await seed_assigned_task(session, employee_id)

    await create_update(session, task_id=task_id, message_id=300)
    await session.commit()

    async def no_existing_update(*args, **kwargs):
        return None

    # Simulate the race where the pre-check misses an existing row and
    # only the unique index stops the duplicate.
    monkeypatch.setattr(
        employee_work_service,
        "_find_update_by_telegram_message",
        no_existing_update,
    )

    with pytest.raises(ConflictError):
        await create_update(session, task_id=task_id, message_id=300)

    # The savepoint rollback must leave the session usable.
    assert await count_updates(session) == 1
