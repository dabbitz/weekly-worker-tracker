from app.database.models import (
    Base,
    Employee,
    Project,
    RegistrationRequest,
    Task,
    TaskAssignment,
)
from tests.conftest import auth_headers


async def test_dashboard_summary_uses_real_counts(client, session):
    headers = await auth_headers(client)

    project = Project(name="Gerçek Proje")
    session.add(project)
    await session.flush()

    session.add_all(
        [
            Employee(full_name="Aktif Çalışan", is_active=True),
            Employee(full_name="Pasif Çalışan", is_active=False),
        ]
    )
    session.add(Task(project_id=project.id, title="Gerçek Görev"))
    session.add(
        RegistrationRequest(
            telegram_user_id=1234,
            telegram_chat_id=1234,
            requested_full_name="Bekleyen",
            status="pending",
        )
    )
    await session.commit()

    response = await client.get("/api/dashboard/summary", headers=headers)
    assert response.status_code == 200
    summary = response.json()
    assert summary["project_count"] == 1
    assert summary["active_employee_count"] == 1
    assert summary["task_count"] == 1
    assert summary["pending_registration_count"] == 1
    assert len(summary["recent_projects"]) == 1
    assert summary["recent_projects"][0]["name"] == "Gerçek Proje"


async def test_dashboard_empty_state_has_zero_counts(client):
    headers = await auth_headers(client)
    response = await client.get("/api/dashboard/summary", headers=headers)
    assert response.status_code == 200
    summary = response.json()
    assert summary == {
        "project_count": 0,
        "active_employee_count": 0,
        "task_count": 0,
        "pending_registration_count": 0,
        "recent_projects": [],
    }


def test_no_project_memberships_table_or_direct_link():
    table_names = set(Base.metadata.tables)

    assert "project_memberships" not in table_names
    assert table_names == {
        "employees",
        "projects",
        "tasks",
        "task_assignments",
        "weekly_task_plans",
        "weekly_plan_generations",
        "task_updates",
        "registration_requests",
        "weekly_manager_reports",
    }

    assert "project_id" not in Employee.__table__.columns
    assert "employee_id" not in Project.__table__.columns

    assert not hasattr(Project, "employees")
    assert not hasattr(Employee, "projects")


async def test_project_team_is_distinct_through_task_assignments(
    client,
    session,
):
    headers = await auth_headers(client)

    project = Project(name="Ekip Projesi")
    second_project = Project(name="Diğer Proje")
    session.add_all([project, second_project])
    await session.flush()

    employee = Employee(full_name="Ortak Çalışan")
    session.add(employee)
    await session.flush()

    first_task = Task(project_id=project.id, title="Görev 1")
    second_task = Task(project_id=project.id, title="Görev 2")
    other_task = Task(project_id=second_project.id, title="Diğer görev")
    session.add_all([first_task, second_task, other_task])
    await session.flush()

    session.add_all(
        [
            TaskAssignment(task_id=first_task.id, employee_id=employee.id),
            TaskAssignment(task_id=second_task.id, employee_id=employee.id),
            TaskAssignment(task_id=other_task.id, employee_id=employee.id),
        ]
    )
    await session.commit()

    response = await client.get(
        f"/api/projects/{project.id}/employees",
        headers=headers,
    )
    assert response.status_code == 200
    employees = response.json()
    assert len(employees) == 1
    assert employees[0]["id"] == employee.id

    detail = await client.get(
        f"/api/employees/{employee.id}",
        headers=headers,
    )
    project_ids = {item["id"] for item in detail.json()["projects"]}
    assert project_ids == {project.id, second_project.id}
