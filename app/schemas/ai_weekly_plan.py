"""Structured schemas for AI-generated weekly plans.

The AI response deliberately uses ISO date strings. Gemini's structured
output support is most reliable with primitive schema types; the backend
converts and validates the values before anything is stored.
"""

from pydantic import BaseModel, Field


class AIWeeklyPlanWeek(BaseModel):
    week_start_date: str = Field(
        min_length=10,
        max_length=10,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="ISO calendar date (YYYY-MM-DD) for the week start.",
    )
    week_end_date: str = Field(
        min_length=10,
        max_length=10,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="ISO calendar date (YYYY-MM-DD) for the week end.",
    )
    target_description: str = Field(
        min_length=1,
        max_length=4000,
        description="Concrete, measurable Turkish target for this week.",
    )
    target_completion_percentage: int = Field(
        ge=0,
        le=100,
        description=(
            "Cumulative completion percentage of the entire task at the "
            "end of this week. Not the weekly increment."
        ),
    )
    rationale: str | None = Field(
        default=None,
        max_length=2000,
        description="Short Turkish explanation of the weekly target.",
    )


class AIWeeklyTaskPlan(BaseModel):
    task_id: int = Field(
        ge=1,
        description="The database task ID supplied in the request.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions made for this task.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Missing data or risks the administrator should review.",
    )
    weeks: list[AIWeeklyPlanWeek] = Field(
        min_length=1,
        description="One entry for each expected week window.",
    )


class AIWeeklyPlanResult(BaseModel):
    tasks: list[AIWeeklyTaskPlan] = Field(
        min_length=1,
        description="One weekly plan group per requested task.",
    )
