from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
