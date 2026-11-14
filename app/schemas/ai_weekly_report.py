"""Strict structured-output schemas for the AI weekly manager report.

Gemini must return exactly this shape. Every narrative item carries at
least one source token, and the backend rejects unknown tokens, invented
numbers/dates and deterministic-classification mismatches before anything
is stored.

Only primitive JSON-schema types and ``Literal`` enums are used so the
Gemini SDK can build the request schema without unsupported keywords.
"""

from typing import Literal

from pydantic import BaseModel, Field


TaskClassification = Literal[
    "reported_completed",
    "met",
    "below_target",
    "partial",
    "no_report",
    "no_target",
    "target_missing",
    "plan_conflict",
    "plan_approved_after_week",
    "no_percentage",
]

InterventionPriority = Literal["high", "medium", "low"]


class AIReportItem(BaseModel):
    """One observation or recommendation with mandatory evidence."""

    text: str = Field(
        min_length=1,
        max_length=2000,
        description=(
            "Turkish sentence. Use only supplied facts and tokens. "
            "Never introduce a new number, date or employee name."
        ),
    )
    source_tokens: list[str] = Field(
        min_length=1,
        max_length=20,
        description=(
            "At least one supplied reference token (E#, T#, P#, U#, W#)."
        ),
    )


class AIProjectAnalysis(BaseModel):
    project_token: str = Field(
        min_length=2,
        max_length=16,
        pattern=r"^P\d+$",
        description="Supplied project token.",
    )
    summary: str = Field(min_length=1, max_length=3000)
    highlights: list[AIReportItem] = Field(default_factory=list)
    risks: list[AIReportItem] = Field(default_factory=list)


class AIEmployeeAnalysis(BaseModel):
    """Activity observation, never a productivity score or ranking."""

    employee_token: str = Field(
        min_length=2,
        max_length=16,
        pattern=r"^E\d+$",
        description="Supplied employee token.",
    )
    summary: str = Field(min_length=1, max_length=3000)
    observations: list[AIReportItem] = Field(default_factory=list)


class AITaskAssessment(BaseModel):
    task_token: str = Field(
        min_length=2,
        max_length=16,
        pattern=r"^T\d+$",
        description="Supplied task token.",
    )
    assessment: str = Field(min_length=1, max_length=3000)
    classification: TaskClassification = Field(
        description=(
            "Must exactly echo the deterministic classification supplied "
            "for this task."
        ),
    )
    source_tokens: list[str] = Field(min_length=1, max_length=20)


class AIManagerIntervention(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    problem: str = Field(min_length=1, max_length=2000)
    affected_project_tokens: list[str] = Field(default_factory=list)
    affected_task_tokens: list[str] = Field(default_factory=list)
    source_tokens: list[str] = Field(
        min_length=1,
        max_length=20,
        description="At least one real reference token as evidence.",
    )
    priority: InterventionPriority = Field(
        description="AI-suggested priority, not an official decision."
    )
    recommended_action: str = Field(min_length=1, max_length=2000)


class AIWeeklyManagerReport(BaseModel):
    """The full A-I narrative. Numbers come only from deterministic facts."""

    general_summary: str = Field(min_length=1, max_length=4000)
    general_highlights: list[AIReportItem] = Field(default_factory=list)
    general_issues: list[AIReportItem] = Field(default_factory=list)
    project_analyses: list[AIProjectAnalysis] = Field(
        default_factory=list
    )
    employee_analyses: list[AIEmployeeAnalysis] = Field(
        default_factory=list
    )
    task_assessments: list[AITaskAssessment] = Field(default_factory=list)
    unmet_work_analysis: list[AIReportItem] = Field(default_factory=list)
    history_comparison: list[AIReportItem] = Field(default_factory=list)
    recommendations: list[AIReportItem] = Field(default_factory=list)
    data_quality_notes: list[AIReportItem] = Field(default_factory=list)
    manager_interventions: list[AIManagerIntervention] = Field(
        default_factory=list,
        max_length=8,
        description="At most eight evidence-backed intervention items.",
    )
    partial_week_note: str | None = Field(
        default=None,
        max_length=1000,
        description=(
            "Required when the week is still in progress. Must contain "
            "the phrase 'Kısmi değerlendirme'."
        ),
    )


class AIProjectMapResult(BaseModel):
    """Per-project map phase result for very large weeks."""

    project_token: str = Field(
        min_length=2,
        max_length=16,
        pattern=r"^P\d+$",
    )
    summary: str = Field(min_length=1, max_length=3000)
    highlights: list[AIReportItem] = Field(default_factory=list)
    risks: list[AIReportItem] = Field(default_factory=list)
    task_assessments: list[AITaskAssessment] = Field(default_factory=list)
    interventions: list[AIManagerIntervention] = Field(
        default_factory=list,
        max_length=4,
    )
