
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
    # Not the percentage of work completed during this week.

    completion_percentage: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "The overall completion percentage of the entire task "
            "at the time of this report. Extract explicitly stated "
            "percentages such as '70% of the task is completed'. "
            "A phrase like 'this week' does not automatically mean "
            "the percentage represents weekly progress. Return null "
            "only if the percentage is absent or its meaning is ambiguous."
        )
    )

    # Current obstacle.

    blocker: str | None = Field(
        default=None,
        description=(
            "An explicitly stated obstacle currently preventing "
            "the work from progressing."
        )
    )

    # Reason for delay.

    delay_reason: str | None = Field(
        default=None,
        description=(
            "The explicitly stated reason for a delay. "
            "Return null if no delay reason is provided."
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
            "The original expected completion time expression "
            "used by the employee, such as 'cuma gününe kadar', "
            "'yarın' or 'önümüzdeki hafta'. Preserve its meaning. "
            "Do not convert it into a calendar date."
        )
    )

    # AI-generated summary.

    summary: str = Field(
        description=(
            "A concise and factual Turkish summary of the "
            "employee's work update."
        )
    )