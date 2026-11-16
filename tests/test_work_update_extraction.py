"""Focused tests for AI work-update extraction rules.

The Gemini model itself cannot run offline, so the behavioural contract
lives in two testable places:

* the extraction instruction and ``WorkUpdate`` field descriptions that
  tell the model how to classify progress, delays and completion dates,
* the deterministic guards applied to AI output before it is shown to
  the employee (``clamp_ai_draft``) or persisted.
"""

import pytest
from sqlalchemy import select

from app.bot.drafts import clamp_ai_draft
from app.database.models import TaskUpdate
from app.schemas.work_update import WorkStatus, WorkUpdate
from app.services.ai_service import SYSTEM_INSTRUCTION
from tests.test_task_update_service import (
    create_update,
    seed_assigned_task,
    seed_worker,
)


def instruction_line(fragment: str) -> str:
    for line in SYSTEM_INSTRUCTION.splitlines():
        if fragment in line:
            return line
    raise AssertionError(
        f"Extraction instruction no longer mentions: {fragment!r}"
    )


@pytest.mark.parametrize(
    ("phrase", "percentage"),
    [
        ("Daha yeni başladık.", 10),
        ("Yarısını tamamladık.", 50),
        ("Çoğu bitti.", 75),
        ("Neredeyse tamamladık.", 90),
        ("İşin tamamını bitirdik.", 100),
    ],
)
def test_instruction_maps_natural_language_progress(
    phrase,
    percentage,
):
    line = instruction_line(phrase)

    assert f"reported_progress_percentage = {percentage}" in line


def test_instruction_keeps_explicit_percentage_first():
    text = " ".join(SYSTEM_INSTRUCTION.split())

    assert "explicitly stated percentage always takes priority" in text
    assert "never the personal contribution share" in text


def test_instruction_forbids_invented_percentages():
    text = " ".join(SYSTEM_INSTRUCTION.split())

    assert "return null" in text
    assert "Never invent a percentage" in text
    assert "return a default value" in text


def test_instruction_separates_delay_from_blocked():
    text = " ".join(SYSTEM_INSTRUCTION.split())

    assert "never set the status to blocked" in text
    assert "Use blocked only when the obstacle actually prevents" in text
    assert "fill both blocker and delay_reason" in text
    assert "A completed task stays completed" in text
    assert "never invent a delay reason" in text


def test_instruction_does_not_treat_event_dates_as_task_eta():
    text = " ".join(SYSTEM_INSTRUCTION.split())

    assert "The date of another event is NOT the task completion date" in text
    assert (
        "Tedarikçi teslimatın 20 Kasım'da yapılacağını söyledi."
        in text
    )
    assert "reported_eta_text = null (20 Kasım is a delivery date)" in text
    assert (
        "The backend normalizes reported_eta_text only" in text
    )


def test_schema_documents_task_eta_scope():
    description = WorkUpdate.model_fields[
        "reported_eta_text"
    ].description

    assert description is not None
    assert "delivery" in description
    assert "Never use" in description


def make_draft(**overrides) -> WorkUpdate:
    data = {
        "task_reference_text": "Kurulum",
        "status": "in_progress",
        "reported_progress_percentage": None,
        "progress_scope": "overall_task",
        "completion_percentage": None,
        "blocker": None,
        "delay_reason": None,
        "next_step": None,
        "reported_eta_text": None,
        "summary": "Kurulum devam ediyor.",
    }
    data.update(overrides)
    if data.get("progress_scope", "overall_task") == "overall_task":
        data["reported_progress_percentage"] = data.get(
            "completion_percentage"
        )
    return WorkUpdate.model_validate(data)


def test_delay_without_blocker_does_not_stay_blocked():
    draft = clamp_ai_draft(
        make_draft(
            status="blocked",
            delay_reason="Kablolama beklenenden uzun sürdü.",
        )
    )

    assert draft.status is WorkStatus.IN_PROGRESS
    assert draft.blocker is None
    assert draft.delay_reason == "Kablolama beklenenden uzun sürdü."


def test_real_obstacle_keeps_blocked_status():
    draft = clamp_ai_draft(
        make_draft(
            status="blocked",
            blocker="Switch ve router ekipmanları teslim edilmedi.",
        )
    )

    assert draft.status is WorkStatus.BLOCKED
    assert draft.blocker == "Switch ve router ekipmanları teslim edilmedi."


def test_blocker_and_delay_are_both_kept():
    draft = clamp_ai_draft(
        make_draft(
            status="blocked",
            blocker="Ekipman teslim edilmedi.",
            delay_reason="Teslim iki gün gecikecek.",
        )
    )

    assert draft.status is WorkStatus.BLOCKED
    assert draft.blocker == "Ekipman teslim edilmedi."
    assert draft.delay_reason == "Teslim iki gün gecikecek."


def test_completed_task_is_not_downgraded():
    draft = clamp_ai_draft(
        make_draft(
            status="completed",
            completion_percentage=100,
            delay_reason="İş iki gün geç teslim edildi.",
        )
    )

    assert draft.status is WorkStatus.COMPLETED
    assert draft.completion_percentage == 100
    assert draft.delay_reason == "İş iki gün geç teslim edildi."


@pytest.mark.parametrize("percentage", [10, 50, 75, 90, 100])
async def test_estimated_percentage_is_persisted_unchanged(
    session,
    percentage,
):
    employee_id = await seed_worker(session)
    task_id = await seed_assigned_task(session, employee_id)

    update = await create_update(
        session,
        task_id=task_id,
        draft=make_draft(
            status="in_progress",
            completion_percentage=percentage,
        ),
        reported_eta_date=None,
    )
    await session.commit()

    await session.rollback()
    stored = await session.scalar(
        select(TaskUpdate).where(TaskUpdate.id == update.id)
    )

    assert stored is not None
    assert stored.completion_percentage == percentage
