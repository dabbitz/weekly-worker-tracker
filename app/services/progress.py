"""Deterministic conversion of reported progress into overall task progress.

The AI only reports a percentage and its scope. This module decides what
``TaskUpdate.completion_percentage`` must contain, which is always the
cumulative progress of the entire task.

``weekly_plan`` percentages are converted with the approved weekly target
and the last known real progress before the week. A weekly or personal
percentage is never stored as the overall task progress directly.
"""

from app.schemas.work_update import ProgressScope


def round_half_up(value: float) -> int:
    """Round a non-negative number deterministically (94.5 -> 95)."""

    return int(value + 0.5)


def convert_weekly_progress(
    *,
    baseline: int | None,
    weekly_progress: int | None,
    weekly_target: int | None,
) -> int | None:
    """Convert weekly-plan progress into cumulative overall task progress.

    Returns None when the baseline or the weekly target is unknown, so a
    weekly percentage is never guessed into an overall value.
    """

    if (
        baseline is None
        or weekly_progress is None
        or weekly_target is None
    ):
        return None

    value = baseline + (weekly_progress / 100) * (
        weekly_target - baseline
    )

    return min(100, max(0, round_half_up(value)))


def compute_overall_progress(
    *,
    reported: int | None,
    scope: ProgressScope,
    baseline: int | None = None,
    weekly_target: int | None = None,
) -> int | None:
    """Return the overall task percentage that may be persisted.

    * ``overall_task`` keeps the reported percentage.
    * ``weekly_plan`` is converted with the approved target and baseline.
    * ``personal_contribution`` and ``unclear`` never become overall
      task progress, so they return None.
    """

    if scope is ProgressScope.OVERALL_TASK:
        return reported

    if scope is ProgressScope.WEEKLY_PLAN:
        return convert_weekly_progress(
            baseline=baseline,
            weekly_progress=reported,
            weekly_target=weekly_target,
        )

    return None
