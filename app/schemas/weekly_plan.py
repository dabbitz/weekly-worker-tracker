from datetime import date, datetime

from pydantic import BaseModel, Field


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
    created_at: datetime
    updated_at: datetime
