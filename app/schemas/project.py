from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.employee import EmployeeSummary
from app.schemas.task import TaskRead


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    location: str | None = Field(default=None, max_length=200)
    expected_completion_date: date | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    location: str | None = Field(default=None, max_length=200)
    expected_completion_date: date | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    location: str | None
    expected_completion_date: date | None
    created_at: datetime
    task_count: int = 0
    employee_count: int = 0


class ProjectDetail(ProjectRead):
    tasks: list[TaskRead] = Field(default_factory=list)
    employees: list[EmployeeSummary] = Field(default_factory=list)


class ProjectOption(BaseModel):
    id: int
    name: str
