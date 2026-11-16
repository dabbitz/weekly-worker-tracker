"""Focused tests for percentage scope and weekly-to-overall conversion."""

from datetime import date, datetime, timezone

from app.bot.drafts import apply_progress_scope, clamp_ai_draft
from app.database.models import TaskUpdate
from app.schemas.work_update import ProgressScope, WorkUpdate
from app.services.ai_service import (
    SYSTEM_INSTRUCTION,
    build_extraction_contents,
)
from app.services.employee_work_service import (
    create_task_update,
    get_progress_baseline,
)
from app.services.progress import compute_overall_progress
from tests.test_employee_work_reports import TODAY, seed_plan, seed_task
from tests.test_employees_tasks import seed_employee


WEEK_END = date(2026, 11, 22)
SECOND_WEEK_START = date(2026, 11, 23)
SECOND_WEEK_END = date(2026, 11, 29)

TELEGRAM_USER_ID = 8801
PRIOR_RECEIVED_AT = datetime(
    2026,
    11,
    20,
    12,
    0,
    tzinfo=timezone.utc,
)


def make_draft(**overrides) -> WorkUpdate:
    data = {
        "task_reference_text": "Şantiye sahası",
        "status": "in_progress",
        "reported_progress_percentage": None,
        "progress_scope": "unclear",
        "completion_percentage": None,
        "blocker": None,
        "delay_reason": None,
        "next_step": None,
        "reported_eta_text": None,
        "summary": "Çalışma devam ediyor.",
    }
    data.update(overrides)
    return WorkUpdate.model_validate(data)


async def seed_worker(session) -> int:
    return await seed_employee(
        session,
        "Kapsam Çalışanı",
        telegram_user_id=TELEGRAM_USER_ID,
    )


async def seed_prior_update(
    session,
    *,
    task_id: int,
    employee_id: int,
    completion_percentage: int,
) -> None:
    session.add(
        TaskUpdate(
            task_id=task_id,
            employee_id=employee_id,
            telegram_user_id=TELEGRAM_USER_ID,
            telegram_chat_id=TELEGRAM_USER_ID,
            telegram_message_id=900,
            original_message="Önceki haftanın raporu.",
            status="in_progress",
            completion_percentage=completion_percentage,
            review_status="approved",
            reviewed_by_employee_id=employee_id,
            reviewed_at=datetime.now(timezone.utc),
            received_at=PRIOR_RECEIVED_AT,
        )
    )
    await session.commit()


# ---------------------------------------------------------------------------
# Deterministic conversion
# ---------------------------------------------------------------------------


def test_first_week_weekly_progress_is_converted_to_overall():
    assert (
        compute_overall_progress(
            reported=90,
            scope=ProgressScope.WEEKLY_PLAN,
            baseline=0,
            weekly_target=50,
        )
        == 45
    )


def test_second_week_weekly_progress_uses_known_baseline():
    assert (
        compute_overall_progress(
            reported=90,
            scope=ProgressScope.WEEKLY_PLAN,
            baseline=45,
            weekly_target=100,
        )
        == 95
    )


def test_explicit_overall_percentage_is_kept():
    assert (
        compute_overall_progress(
            reported=90,
            scope=ProgressScope.OVERALL_TASK,
        )
        == 90
    )


def test_personal_contribution_never_becomes_overall_task_progress():
    assert (
        compute_overall_progress(
            reported=90,
            scope=ProgressScope.PERSONAL_CONTRIBUTION,
            baseline=0,
            weekly_target=50,
        )
        is None
    )


def test_unclear_scope_is_not_guessed_as_overall_task():
    assert (
        compute_overall_progress(
            reported=90,
            scope=ProgressScope.UNCLEAR,
            baseline=0,
            weekly_target=50,
        )
        is None
    )


def test_weekly_progress_without_baseline_is_not_converted():
    assert (
        compute_overall_progress(
            reported=90,
            scope=ProgressScope.WEEKLY_PLAN,
            baseline=None,
            weekly_target=100,
        )
        is None
    )


def test_overall_task_scope_keeps_the_reported_percentage():
    draft = apply_progress_scope(
        clamp_ai_draft(
            make_draft(
                reported_progress_percentage=90,
                progress_scope="overall_task",
                completion_percentage=90,
            )
        )
    )

    assert draft.progress_scope is ProgressScope.OVERALL_TASK
    assert draft.completion_percentage == 90


def test_personal_contribution_scope_has_no_overall_percentage():
    draft = apply_progress_scope(
        clamp_ai_draft(
            make_draft(
                reported_progress_percentage=90,
                progress_scope="personal_contribution",
                completion_percentage=90,
            )
        ),
        baseline=0,
        weekly_target=50,
    )

    assert draft.progress_scope is ProgressScope.PERSONAL_CONTRIBUTION
    assert draft.completion_percentage is None


def test_mismatched_work_is_not_converted_from_a_weekly_percentage():
    # The selected task/plan covers ground cleaning, while the message
    # describes unrelated network work. The conservative scope is unclear.
    draft = apply_progress_scope(
        clamp_ai_draft(
            make_draft(
                reported_progress_percentage=90,
                progress_scope="unclear",
                completion_percentage=90,
            )
        ),
        baseline=0,
        weekly_target=50,
    )

    assert draft.completion_percentage is None


def test_instruction_requires_the_weekly_context_to_match():
    text = " ".join(SYSTEM_INSTRUCTION.split())

    assert "must actually match the plan description" in text
    assert "clearly differs from the selected task" in text
    assert "TASK AND WEEKLY PLAN CONTEXT" in text


def test_extraction_contents_include_task_and_plan_context():
    contents = build_extraction_contents(
        "Bu haftaki hazırlıkların %90'ını tamamladık.",
        {
            "task_title": "Ağ ve Sunucu Altyapısının Kurulumu",
            "weekly_plan": {
                "description": "Kurulum hazırlıkları",
                "week_start_date": TODAY.isoformat(),
                "week_end_date": WEEK_END.isoformat(),
                "target_completion_percentage": 50,
            },
        },
    )

    assert "TASK AND WEEKLY PLAN CONTEXT" in contents
    assert "Ağ ve Sunucu Altyapısının Kurulumu" in contents
    assert "Kurulum hazırlıkları" in contents
    assert "Bu haftaki hazırlıkların" in contents


def test_clamp_keeps_non_overall_percentage_out_of_completion_field():
    draft = clamp_ai_draft(
        make_draft(
            reported_progress_percentage=90,
            progress_scope="weekly_plan",
            completion_percentage=90,
        )
    )

    assert draft.reported_progress_percentage == 90
    assert draft.completion_percentage is None


def test_apply_progress_scope_sets_the_computed_overall_value():
    draft = apply_progress_scope(
        make_draft(
            reported_progress_percentage=90,
            progress_scope="weekly_plan",
        ),
        baseline=0,
        weekly_target=50,
    )

    assert draft.reported_progress_percentage == 90
    assert draft.completion_percentage == 45


# ---------------------------------------------------------------------------
# Persistence: completion_percentage always means the whole task
# ---------------------------------------------------------------------------


async def test_first_week_report_is_saved_as_converted_overall(session):
    employee_id = await seed_worker(session)
    _, task_id = await seed_task(
        session,
        employee_ids=(employee_id,),
        planned_start_date=TODAY,
    )

    plan_id = await seed_plan(
        session,
        task_id,
        TODAY,
        WEEK_END,
        percentage=50,
    )

    update = await create_task_update(
        session,
        telegram_user_id=TELEGRAM_USER_ID,
        telegram_chat_id=TELEGRAM_USER_ID,
        telegram_message_id=100,
        task_id=task_id,
        original_message="Planın %90'ını tamamladık.",
        draft=make_draft(
            reported_progress_percentage=90,
            progress_scope="weekly_plan",
        ),
        weekly_plan_id=plan_id,
        today=TODAY,
    )

    assert update.completion_percentage == 45


async def test_second_week_report_is_saved_with_prior_real_baseline(
    session,
):
    employee_id = await seed_worker(session)
    _, task_id = await seed_task(
        session,
        employee_ids=(employee_id,),
        planned_start_date=date(2026, 11, 9),
    )
    await seed_prior_update(
        session,
        task_id=task_id,
        employee_id=employee_id,
        completion_percentage=45,
    )

    plan_id = await seed_plan(
        session,
        task_id,
        SECOND_WEEK_START,
        SECOND_WEEK_END,
        percentage=100,
    )

    update = await create_task_update(
        session,
        telegram_user_id=TELEGRAM_USER_ID,
        telegram_chat_id=TELEGRAM_USER_ID,
        telegram_message_id=101,
        task_id=task_id,
        original_message="Planın %90'ını tamamladık.",
        draft=make_draft(
            reported_progress_percentage=90,
            progress_scope="weekly_plan",
        ),
        weekly_plan_id=plan_id,
        today=SECOND_WEEK_START,
    )

    assert update.completion_percentage == 95


async def test_overall_scope_report_is_saved_as_given(session):
    employee_id = await seed_worker(session)
    _, task_id = await seed_task(
        session,
        employee_ids=(employee_id,),
        planned_start_date=TODAY,
    )

    update = await create_task_update(
        session,
        telegram_user_id=TELEGRAM_USER_ID,
        telegram_chat_id=TELEGRAM_USER_ID,
        telegram_message_id=102,
        task_id=task_id,
        original_message="Görevin %90'ını tamamladık.",
        draft=make_draft(
            reported_progress_percentage=90,
            progress_scope="overall_task",
        ),
        today=TODAY,
    )

    assert update.completion_percentage == 90


async def test_personal_contribution_is_saved_without_overall_percentage(
    session,
):
    employee_id = await seed_worker(session)
    _, task_id = await seed_task(
        session,
        employee_ids=(employee_id,),
        planned_start_date=TODAY,
    )

    plan_id = await seed_plan(
        session,
        task_id,
        TODAY,
        WEEK_END,
        percentage=50,
    )

    update = await create_task_update(
        session,
        telegram_user_id=TELEGRAM_USER_ID,
        telegram_chat_id=TELEGRAM_USER_ID,
        telegram_message_id=103,
        task_id=task_id,
        original_message="Kendi işimin %90'ını bitirdim.",
        draft=make_draft(
            reported_progress_percentage=90,
            progress_scope="personal_contribution",
        ),
        weekly_plan_id=plan_id,
        today=TODAY,
    )

    assert update.completion_percentage is None


async def test_unclear_scope_is_saved_without_overall_percentage(session):
    employee_id = await seed_worker(session)
    _, task_id = await seed_task(
        session,
        employee_ids=(employee_id,),
        planned_start_date=TODAY,
    )

    update = await create_task_update(
        session,
        telegram_user_id=TELEGRAM_USER_ID,
        telegram_chat_id=TELEGRAM_USER_ID,
        telegram_message_id=104,
        task_id=task_id,
        original_message="İşin %90'ını tamamladık.",
        draft=make_draft(
            reported_progress_percentage=90,
            progress_scope="unclear",
        ),
        today=TODAY,
    )

    assert update.completion_percentage is None


async def test_unknown_baseline_is_not_estimated(session):
    employee_id = await seed_worker(session)
    _, task_id = await seed_task(
        session,
        employee_ids=(employee_id,),
        planned_start_date=date(2026, 11, 9),
    )
    plan_id = await seed_plan(
        session,
        task_id,
        TODAY,
        WEEK_END,
        percentage=100,
    )

    update = await create_task_update(
        session,
        telegram_user_id=TELEGRAM_USER_ID,
        telegram_chat_id=TELEGRAM_USER_ID,
        telegram_message_id=105,
        task_id=task_id,
        original_message="Planın %90'ını tamamladık.",
        draft=make_draft(
            reported_progress_percentage=90,
            progress_scope="weekly_plan",
        ),
        weekly_plan_id=plan_id,
        today=TODAY,
    )

    assert update.completion_percentage is None


async def test_previous_weekly_target_is_not_actual_progress(session):
    _, task_id = await seed_task(
        session,
        planned_start_date=date(2026, 11, 9),
    )
    await seed_plan(
        session,
        task_id,
        date(2026, 11, 9),
        date(2026, 11, 15),
        percentage=50,
    )

    baseline = await get_progress_baseline(
        session,
        task_id=task_id,
        week_start_date=TODAY,
        task_planned_start_date=date(2026, 11, 9),
    )

    assert baseline is None
