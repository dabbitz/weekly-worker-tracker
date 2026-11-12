from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class WeeklyPlanStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class WeeklyPlanSource(str, Enum):
    MANUAL = "manual"
    AI = "ai"


class WeeklyPlanBase(BaseModel):
    week_start_date: date
    week_end_date: date
    target_description: str = Field(min_length=1, max_length=4000)
    target_completion_percentage: int | None = Field(
        default=None,
        ge=0,
        le=100,
    )


class WeeklyPlanCreate(WeeklyPlanBase):
    task_id: int = Field(gt=0)


class WeeklyPlanUpdate(BaseModel):
    task_id: int | None = Field(default=None, gt=0)
    week_start_date: date | None = None
    week_end_date: date | None = None
    target_description: str | None = Field(
        default=None,
        min_length=1,
        max_length=4000,
    )
    target_completion_percentage: int | None = Field(
        default=None,
        ge=0,
        le=100,
    )


class WeeklyPlanApprove(BaseModel):
    replace_existing: bool = False


class WeeklyPlanRead(BaseModel):
    id: int
    task_id: int
    task_title: str
    project_id: int
    project_name: str
    week_start_date: date
    week_end_date: date
    target_description: str
    target_completion_percentage: int | None
    status: WeeklyPlanStatus
    source: WeeklyPlanSource
    generation_id: int | None = None
    generation_request_id: str | None = None
    ai_rationale: str | None = None
    ai_assumptions: str | None = None
    ai_warnings: str | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AIPlanGenerateRequest(BaseModel):
    task_ids: list[int] = Field(min_length=1, max_length=20)
    extra_instructions: str | None = Field(
        default=None,
        max_length=4000,
    )
    request_id: str | None = Field(
        default=None,
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )


class AIPlanGenerateResponse(BaseModel):
    generation_id: int
    request_id: str
    plan_count: int
    tasks: list[int] = Field(default_factory=list)
    plans: list[WeeklyPlanRead] = Field(default_factory=list)
