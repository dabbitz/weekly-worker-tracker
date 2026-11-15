
from enum import Enum
from pydantic import BaseModel, Field


class WorkStatus(str, Enum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    NOT_STARTED = "not_started"
    UNKNOWN = "unknown"


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

    # Overall completion percentage of the entire task.
    # Not the percentage of work completed during this week and not the
    # employee's personal contribution share.

    completion_percentage: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "The overall completion percentage of the entire task "
            "at the time of this report. Use an explicitly stated "
            "number such as '70% of the task is completed' exactly. "
            "When no number is given but the message clearly states "
            "how much of the task is done ('we just started', 'half of "
            "it is done', 'most of it is done', 'nearly finished', "
            "'we finished the whole job'), infer one approximate "
            "percentage between 0 and 100. Return null when the "
            "message does not support a defensible estimate. A phrase "
            "like 'this week' does not automatically mean the "
            "percentage represents weekly progress."
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