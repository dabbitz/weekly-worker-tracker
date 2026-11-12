from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel

from app.schemas.common import Page
from app.schemas.weekly_plan import WeeklyPlanStatus
from app.schemas.work_update import WorkStatus


class ReportReviewStatus(str, Enum):
    """Employee review state of an AI-structured report.

    ``approved`` means the employee reviewed and confirmed the draft.
    It never represents an administrator decision.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReportListItem(BaseModel):
    id: int
    received_at: datetime
    employee_id: int | None
    employee_name: str | None
    project_id: int | None
    project_name: str | None
    task_id: int | None
    task_title: str | None
    completion_percentage: int | None
    status: WorkStatus
    has_blocker: bool
    has_delay: bool
    review_status: ReportReviewStatus
    weekly_plan_id: int | None
    has_weekly_plan: bool


class ReportStats(BaseModel):
    total: int
    blocked_count: int
    with_blocker_count: int
    with_delay_count: int
    completed_count: int


class ReportListResponse(Page[ReportListItem]):
    stats: ReportStats


class ReportWeeklyPlan(BaseModel):
    id: int
    target_description: str
    target_completion_percentage: int | None
    week_start_date: date
    week_end_date: date
    status: WeeklyPlanStatus


class ReportDetail(ReportListItem):
    task_description: str | None
    original_message: str
    task_reference_text: str | None
    blocker: str | None
    delay_reason: str | None
    next_step: str | None
    reported_eta_text: str | None
    reported_eta_date: date | None
    reported_eta_weekday: str | None
    summary: str | None
    ai_model: str | None
    reviewed_at: datetime | None
    reviewed_by_employee_id: int | None
    reviewed_by_employee_name: str | None
    weekly_plan: ReportWeeklyPlan | None
