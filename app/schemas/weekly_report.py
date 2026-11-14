"""API contracts for the weekly manager report feature."""

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Page


class WeeklyManagerReportStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class WeekPeriod(BaseModel):
    week_start_date: date
    week_end_date: date
    label: str
    is_current_week: bool
    is_partial_week: bool
    is_completed: bool
    is_future: bool
    is_default: bool


class WeeklyReportPeriodsResponse(BaseModel):
    periods: list[WeekPeriod]
    default_week_start_date: date
    current_week_start_date: date
    timezone: str = "Europe/Istanbul"


class PreviewWarning(BaseModel):
    code: str
    message: str


class PreviewProject(BaseModel):
    project_token: str
    name: str
    task_count: int
    report_count: int


class WeeklyReportPreview(BaseModel):
    week_start_date: date
    week_end_date: date
    label: str
    is_partial_week: bool
    is_current_week: bool
    project_count: int
    task_count: int
    plan_count: int
    report_count: int
    pending_review_report_count: int
    completed_task_count: int
    in_progress_task_count: int
    blocked_task_count: int
    not_started_task_count: int
    no_report_task_count: int
    unassigned_task_count: int
    plan_conflict_count: int
    missing_target_percentage_count: int
    intervention_candidate_count: int
    has_data: bool
    projects: list[PreviewProject] = Field(default_factory=list)
    warnings: list[PreviewWarning] = Field(default_factory=list)


class WeeklyReportCreate(BaseModel):
    week_start_date: date
    request_id: str = Field(
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    extra_instructions: str | None = Field(
        default=None,
        max_length=2000,
    )


class WeeklyReportListItem(BaseModel):
    id: int
    week_start_date: date
    week_end_date: date
    version: int
    status: WeeklyManagerReportStatus
    model: str | None
    is_partial_week: bool
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    has_narrative: bool
    project_count: int = 0
    task_count: int = 0
    report_count: int = 0
    intervention_count: int = 0


class WeeklyReportListResponse(Page[WeeklyReportListItem]):
    pass


class NarrativeSegment(BaseModel):
    type: Literal["text", "reference"]
    text: str | None = None
    token: str | None = None
    kind: str | None = None
    ref_id: int | None = None
    label: str | None = None
    href: str | None = None


class NarrativeBlock(BaseModel):
    segments: list[NarrativeSegment]
    sources: list[NarrativeSegment] = Field(default_factory=list)


class NarrativeProjectView(BaseModel):
    project: NarrativeSegment
    summary: list[NarrativeSegment]
    highlights: list[NarrativeBlock] = Field(default_factory=list)
    risks: list[NarrativeBlock] = Field(default_factory=list)


class NarrativeEmployeeView(BaseModel):
    employee: NarrativeSegment
    summary: list[NarrativeSegment]
    observations: list[NarrativeBlock] = Field(default_factory=list)


class NarrativeTaskView(BaseModel):
    task: NarrativeSegment
    assessment: list[NarrativeSegment]
    classification: str
    classification_label: str
    sources: list[NarrativeSegment] = Field(default_factory=list)


class NarrativeInterventionView(BaseModel):
    title: list[NarrativeSegment]
    problem: list[NarrativeSegment]
    recommended_action: list[NarrativeSegment]
    priority: Literal["high", "medium", "low"]
    affected_projects: list[NarrativeSegment] = Field(default_factory=list)
    affected_tasks: list[NarrativeSegment] = Field(default_factory=list)
    sources: list[NarrativeSegment] = Field(default_factory=list)


class NarrativeView(BaseModel):
    source: Literal["ai", "deterministic_empty"]
    general_summary: list[NarrativeSegment]
    general_highlights: list[NarrativeBlock] = Field(default_factory=list)
    general_issues: list[NarrativeBlock] = Field(default_factory=list)
    project_analyses: list[NarrativeProjectView] = Field(
        default_factory=list
    )
    employee_analyses: list[NarrativeEmployeeView] = Field(
        default_factory=list
    )
    task_assessments: list[NarrativeTaskView] = Field(default_factory=list)
    unmet_work_analysis: list[NarrativeBlock] = Field(default_factory=list)
    history_comparison: list[NarrativeBlock] = Field(default_factory=list)
    recommendations: list[NarrativeBlock] = Field(default_factory=list)
    data_quality_notes: list[NarrativeBlock] = Field(default_factory=list)
    manager_interventions: list[NarrativeInterventionView] = Field(
        default_factory=list
    )
    partial_week_note: list[NarrativeSegment] | None = None


class WeeklyReportDetail(WeeklyReportListItem):
    request_id: str
    extra_instructions: str | None
    metrics_snapshot: dict
    data_quality: list[dict]
    narrative: dict | None
    narrative_view: NarrativeView | None
    references: dict
    intervention_candidates: list[dict] = Field(default_factory=list)
