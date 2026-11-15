from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmployeeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    role: str | None
    is_active: bool


class EmployeeRead(EmployeeSummary):
    telegram_user_id: int | None
    created_at: datetime
    task_count: int = 0
    project_count: int = 0


class EmployeeUpdate(BaseModel):
    """Administrator-editable employee fields.

    ``role`` is the employee's job title / position. It is not an
    authorization role: the dashboard cannot grant admin rights here.
    """

    role: str | None = Field(default=None, max_length=80)
