from pydantic import BaseModel, Field

from app.schemas.employee import EmployeeRead
from app.schemas.project import ProjectOption
from app.schemas.task import TaskRead


class EmployeeDetail(EmployeeRead):
    assigned_tasks: list[TaskRead] = Field(default_factory=list)
    projects: list[ProjectOption] = Field(default_factory=list)
