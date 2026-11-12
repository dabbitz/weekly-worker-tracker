from pydantic import BaseModel

from app.schemas.project import ProjectRead


class DashboardSummary(BaseModel):
    project_count: int
    active_employee_count: int
    task_count: int
    pending_registration_count: int
    recent_projects: list[ProjectRead]
