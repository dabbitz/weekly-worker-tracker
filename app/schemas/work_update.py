
from enum import Enum
from pydantic import BaseModel, Field


class WorkStatus(str, Enum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    NOT_STARTED = "not_started"
    UNKNOWN = "unknown"


class ProgressScope(str, Enum):
    """What a reported progress percentage refers to."""

    OVERALL_TASK = "overall_task"
    WEEKLY_PLAN = "weekly_plan"
    PERSONAL_CONTRIBUTION = "personal_contribution"
    UNCLEAR = "unclear"


class WorkUpdate(BaseModel):

    # The task name or description extracted from the message.
    # This is NOT a database task ID.

    task_reference_text: str | None = Field(
        default=None,
        description=(
            "A concise description of the task mentioned "
            "by the employee. Do not generate database IDs."
        )
    )

    # Current reported task status.

    status: WorkStatus = Field(
        description=(
            "The current status of the reported work."
        )
    )

    # Progress percentage exactly as reported in the message, before any
    # backend conversion. It may refer to the whole task, the current
    # weekly plan, or only the employee's personal contribution.

    reported_progress_percentage: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "The progress percentage stated or clearly implied in the "
            "employee's message. Use an explicitly stated number such as "
            "'70%' exactly. When no number is given but the message "
            "clearly describes how much of the reported scope is done "
            "('we just started', 'half of it is done', 'most of it is "
            "done', 'nearly finished', 'we finished the whole job'), "
            "infer one approximate percentage between 0 and 100. Return "
            "null when the message does not support a defensible "
            "estimate."
        )
    )

    # What the reported percentage refers to.

    progress_scope: ProgressScope = Field(
        default=ProgressScope.UNCLEAR,
        description=(
            "The scope of reported_progress_percentage. Use exactly one "
            "of: 'overall_task' (total progress of the entire task), "
            "'weekly_plan' (progress of the work planned for the "
            "current weekly plan), 'personal_contribution' (progress of "
            "only the employee's own assigned part) or 'unclear' when "
            "the message does not provide enough evidence. Consider the "
            "task title, the weekly plan description, the reporting "
            "period and the employee's wording. Never guess a scope and "
            "never default to 'overall_task'."
        )
    )

    # Overall completion percentage of the entire task.
    # Calculated by the backend; the AI must never fill this field.

    completion_percentage: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "The overall completion percentage of the entire task at "
            "the time of this report. This field is calculated by the "
            "backend after the AI response. Always return null and "
            "never copy reported_progress_percentage into it. Do not "
            "convert weekly or personal progress into overall task "
            "progress yourself."
        )
    )

    # Current obstacle.

    blocker: str | None = Field(
        default=None,
        description=(
            "An explicitly stated obstacle currently preventing "
            "the work from continuing. A delay alone is not a blocker."
        )
    )

    # Reason for delay.

    delay_reason: str | None = Field(
        default=None,
        description=(
            "The explicitly stated delay and its stated cause when "
            "work continues but the schedule is slipping. Return null "
            "if no delay is reported, and never invent a cause."
        )
    )

    # Next planned action.

    next_step: str | None = Field(
        default=None,
        description=(
            "The next action explicitly stated or clearly "
            "committed to by the employee. Do not invent actions."
        )
    )

    # Original expected completion expression.

    reported_eta_text: str | None = Field(
        default=None,
        description=(
            "The original expected completion time expression for "
            "finishing the task itself, such as 'cuma gününe kadar', "
            "'yarın' or 'önümüzdeki hafta'. Preserve its meaning. "
            "Never use a delivery, material, meeting, inspection or "
            "visit date here. Do not convert it into a calendar date."
        )
    )

    # AI-generated summary.

    summary: str = Field(
        description=(
            "A concise and factual Turkish summary of the "
            "employee's work update."
        )
    )