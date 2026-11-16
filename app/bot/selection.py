"""Task selection snapshots and stale-preview checks.

The callback's task id is only a lookup key. Every use re-resolves the
task and the approved weekly plan from the database, and the selected
plan is stored as a serializable snapshot. At confirmation time the
current context must still match that snapshot.
"""

from app.services.employee_work_service import (
    EmployeeTaskContext,
    EmployeeWeeklyPlan,
)


def plan_to_data(plan: EmployeeWeeklyPlan | None) -> dict | None:
    if plan is None:
        return None

    return {
        "id": plan.id,
        "week_start_date": plan.week_start_date.isoformat(),
        "week_end_date": plan.week_end_date.isoformat(),
        "target_description": plan.target_description,
        "target_completion_percentage": (
            plan.target_completion_percentage
        ),
    }


def selection_data(
    context: EmployeeTaskContext,
    *,
    telegram_user_id: int,
    chat_id: int,
) -> dict:
    """Build the initial FSM data for a freshly selected task."""

    return {
        "telegram_user_id": telegram_user_id,
        "chat_id": chat_id,
        "task_id": context.task_id,
        "task_title": context.title,
        "project_name": context.project_name,
        "plan": plan_to_data(context.weekly_plan),
        "plan_conflict": context.plan_conflict,
        "source_message_id": None,
        "source_message_date": None,
        "original_message": None,
        "draft": None,
        "progress_baseline": None,
        "reported_eta_date": None,
        "ai_model": None,
        "confirmation_token": None,
        "field_to_edit": None,
        "preview_message_id": None,
    }


def context_matches_selection(
    data: dict,
    context: EmployeeTaskContext,
) -> bool:
    """Return True when the preview still reflects the real context.

    A plan edit, replacement, removal or a new conflicting plan changes
    the answer, and the old preview must not be persisted.
    """

    if data.get("task_id") != context.task_id:
        return False

    if bool(data.get("plan_conflict")) != context.plan_conflict:
        return False

    stored_plan = data.get("plan")
    current_plan = plan_to_data(context.weekly_plan)

    return stored_plan == current_plan
