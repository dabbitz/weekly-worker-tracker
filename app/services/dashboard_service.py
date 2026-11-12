from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Employee, Project, RegistrationRequest, Task
from app.schemas.dashboard import DashboardSummary
from app.services.project_service import list_projects


async def get_dashboard_summary(
    session: AsyncSession,
) -> DashboardSummary:
    project_count = int(
        (await session.execute(select(func.count(Project.id)))).scalar_one()
    )
    active_employee_count = int(
        (
            await session.execute(
                select(func.count(Employee.id)).where(
                    Employee.is_active.is_(True)
                )
            )
        ).scalar_one()
    )
    task_count = int(
        (await session.execute(select(func.count(Task.id)))).scalar_one()
    )
    pending_registration_count = int(
        (
            await session.execute(
                select(func.count(RegistrationRequest.id)).where(
                    RegistrationRequest.status == "pending"
                )
            )
        ).scalar_one()
    )

    recent = await list_projects(
        session,
        page=1,
        page_size=5,
    )

    return DashboardSummary(
        project_count=project_count,
        active_employee_count=active_employee_count,
        task_count=task_count,
        pending_registration_count=pending_registration_count,
        recent_projects=recent.items,
    )
