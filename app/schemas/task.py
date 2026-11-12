from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.employee import EmployeeSummary


class TaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    description: str | None = Field(default=None, max_length=8000)
    planned_start_date: date | None = None
    planned_due_date: date | None = None


class TaskCreate(TaskBase):
    project_id: int = Field(gt=0)
    employee_ids: list[int] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    project_id: int | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, min_length=1, max_length=250)
    description: str | None = Field(default=None, max_length=8000)
    planned_start_date: date | None = None
    planned_due_date: date | None = None


class AssignmentUpdate(BaseModel):
    employee_ids: list[int] = Field(default_factory=list)


class TaskRead(BaseModel):
    id: int
    project_id: int
    project_name: str
    title: str
    description: str | None
    planned_start_date: date | None
    planned_start_weekday: str | None
    planned_due_date: date | None
    planned_due_weekday: str | None
    created_at: datetime
    assigned_employees: list[EmployeeSummary] = Field(default_factory=list)
    weekly_plan_count: int = 0
