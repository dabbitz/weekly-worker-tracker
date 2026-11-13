from datetime import date, datetime, timezone

import pytest
from sqlalchemy import func, select

from app.database.models import (
    Employee,
    Project,
    RegistrationRequest,
    Task,
    TaskAssignment,
    TaskUpdate,
    WeeklyTaskPlan,
)
from tests.conftest import auth_headers


WEEK_START = date(2026, 11, 16)
WEEK_END = date(2026, 11, 22)
NOW = datetime(2026, 11, 18, 9, 0, tzinfo=timezone.utc)


async def make_employee(
    session,
    full_name: str,
    *,
    telegram_user_id: int | None = None,
) -> Employee:
    employee = Employee(
        full_name=full_name,
        telegram_user_id=telegram_user_id,
    )
    session.add(employee)
    await session.flush()
    return employee


async def make_project_and_task(
    session,
    *,
    project_name: str = "Silme Projesi",
    task_title: str = "Silinecek görev",
    employees: list[Employee] | None = None,
) -> tuple[Project, Task]:
    project = Project(name=project_name)
    session.add(project)
    await session.flush()

    task = Task(project_id=project.id, title=task_title)
    session.add(task)
    await session.flush()

    for employee in employees or []:
        session.add(
            TaskAssignment(
                task_id=task.id,
                employee_id=employee.id,
            )
        )

    await session.flush()
    return project, task


async def make_plan(
    session,
    task: Task,
    *,
    status: str = "draft",
    week_start: date = WEEK_START,
    week_end: date = WEEK_END,
    description: str = "Haftalık hedef",
) -> WeeklyTaskPlan:
    plan = WeeklyTaskPlan(
        task_id=task.id,
        week_start_date=week_start,
        week_end_date=week_end,
        target_description=description,
        target_completion_percentage=50,
        status=status,
        source="manual",
        approved_at=NOW if status == "approved" else None,
    )
    session.add(plan)
    await session.flush()
    return plan


async def make_update(
    session,
    *,
    message_id: int,
    task: Task | None = None,
    plan: WeeklyTaskPlan | None = None,
    employee: Employee | None = None,
    review_status: str = "pending",
    reviewed_by: Employee | None = None,
) -> TaskUpdate:
    reviewed = review_status != "pending"

    update = TaskUpdate(
        task_id=task.id if task is not None else None,
        weekly_plan_id=plan.id if plan is not None else None,
        employee_id=employee.id if employee is not None else None,
        telegram_user_id=700000 + message_id,
        telegram_chat_id=700000 + message_id,
        telegram_message_id=message_id,
        original_message="İş raporu içeriği.",
        status="in_progress",
        completion_percentage=40,
        review_status=review_status,
        reviewed_by_employee_id=(
            reviewed_by.id if reviewed and reviewed_by is not None else None
        ),
        reviewed_at=NOW if reviewed else None,
        received_at=NOW,
    )
    session.add(update)
    await session.flush()
    return update


async def count(session, model) -> int:
    return int(
        (
            await session.execute(select(func.count()).select_from(model))
        ).scalar_one()
    )


async def row_exists(session, model, row_id: int) -> bool:
    return (
        await session.scalar(select(model.id).where(model.id == row_id))
    ) is not None


async def test_delete_endpoints_require_admin_token(client):
    endpoints = [
        "/api/projects/1",
        "/api/employees/1",
        "/api/tasks/1",
        "/api/weekly-plans/1",
        "/api/registration-requests/1",
        "/api/reports/1",
    ]

    for endpoint in endpoints:
        response = await client.delete(endpoint)
        assert response.status_code == 401, endpoint


async def test_project_delete_preview_and_success(client, session):
    headers = await auth_headers(client)
    employee = await make_employee(session, "Ayşe Yılmaz")
    project, task = await make_project_and_task(
        session,
        employees=[employee],
    )
    plan = await make_plan(session, task)
    unrelated, unrelated_task = await make_project_and_task(
        session,
        project_name="İlgisiz proje",
        task_title="İlgisiz görev",
    )
    await session.commit()

    preview = await client.get(
        f"/api/projects/{project.id}/deletion-preview",
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json() == {
        "id": project.id,
        "name": project.name,
        "task_count": 1,
        "assignment_count": 1,
        "weekly_plan_count": 1,
        "report_count": 0,
    }

    response = await client.delete(
        f"/api/projects/{project.id}",
        headers=headers,
    )
    assert response.status_code == 204, response.text

    assert not await row_exists(session, Project, project.id)
    assert not await row_exists(session, Task, task.id)
    assert not await row_exists(session, WeeklyTaskPlan, plan.id)
    assert (
        await session.scalar(
            select(func.count())
            .select_from(TaskAssignment)
            .where(TaskAssignment.task_id == task.id)
        )
    ) == 0

    # Unrelated project/task and the employee are preserved.
    assert await row_exists(session, Project, unrelated.id)
    assert await row_exists(session, Task, unrelated_task.id)
    assert await row_exists(session, Employee, employee.id)


async def test_project_delete_blocked_by_task_and_plan_reports(
    client,
    session,
):
    headers = await auth_headers(client)
    project, task = await make_project_and_task(session)
    plan = await make_plan(session, task)
    task_report = await make_update(
        session,
        message_id=1,
        task=task,
    )
    plan_report = await make_update(
        session,
        message_id=2,
        plan=plan,
    )
    await session.commit()

    response = await client.delete(
        f"/api/projects/{project.id}",
        headers=headers,
    )
    assert response.status_code == 409, response.text
    assert "2" in response.json()["detail"]

    # No partial deletion happened.
    assert await row_exists(session, Project, project.id)
    assert await row_exists(session, Task, task.id)
    assert await row_exists(session, WeeklyTaskPlan, plan.id)
    assert await row_exists(session, TaskUpdate, task_report.id)
    assert await row_exists(session, TaskUpdate, plan_report.id)


async def test_employee_delete_removes_assignments_and_keeps_request(
    client,
    session,
):
    headers = await auth_headers(client)
    employee = await make_employee(session, "Mehmet Demir", telegram_user_id=11)
    project, task = await make_project_and_task(
        session,
        employees=[employee],
    )
    request = RegistrationRequest(
        telegram_user_id=11,
        telegram_chat_id=11,
        requested_full_name=employee.full_name,
        employee_id=employee.id,
        status="pending",
    )
    session.add(request)
    await session.commit()

    response = await client.delete(
        f"/api/employees/{employee.id}",
        headers=headers,
    )
    assert response.status_code == 204, response.text

    assert not await row_exists(session, Employee, employee.id)
    assert (
        await session.scalar(
            select(func.count())
            .select_from(TaskAssignment)
            .where(TaskAssignment.employee_id == employee.id)
        )
    ) == 0
    assert await row_exists(session, Project, project.id)
    assert await row_exists(session, Task, task.id)

    # The delete ran in a different session, so drop the cached instance
    # before reading the persisted row.
    request_id = request.id
    session.expire_all()
    stored_request = await session.get(RegistrationRequest, request_id)
    assert stored_request is not None
    assert stored_request.employee_id is None


async def test_employee_delete_blocked_as_report_author(client, session):
    headers = await auth_headers(client)
    employee = await make_employee(session, "Rapor Sahibi")
    _, task = await make_project_and_task(session)
    report = await make_update(
        session,
        message_id=3,
        task=task,
        employee=employee,
    )
    await session.commit()

    response = await client.delete(
        f"/api/employees/{employee.id}",
        headers=headers,
    )
    assert response.status_code == 409, response.text
    assert "1" in response.json()["detail"]
    assert await row_exists(session, Employee, employee.id)
    assert await row_exists(session, TaskUpdate, report.id)


async def test_employee_delete_blocked_as_report_reviewer(client, session):
    headers = await auth_headers(client)
    author = await make_employee(session, "Raporu Yazan")
    reviewer = await make_employee(session, "Raporu Onaylayan")
    _, task = await make_project_and_task(session)
    report = await make_update(
        session,
        message_id=4,
        task=task,
        employee=author,
        review_status="approved",
        reviewed_by=reviewer,
    )
    await session.commit()

    response = await client.delete(
        f"/api/employees/{reviewer.id}",
        headers=headers,
    )
    assert response.status_code == 409, response.text
    assert await row_exists(session, Employee, reviewer.id)
    assert await row_exists(session, TaskUpdate, report.id)


async def test_task_delete_removes_assignments_and_plans(client, session):
    headers = await auth_headers(client)
    first = await make_employee(session, "Birinci Çalışan")
    second = await make_employee(session, "İkinci Çalışan")
    project, task = await make_project_and_task(
        session,
        employees=[first, second],
    )
    draft = await make_plan(session, task)
    approved = await make_plan(
        session,
        task,
        status="approved",
        week_start=date(2026, 11, 23),
        week_end=date(2026, 11, 29),
    )
    await session.commit()

    response = await client.delete(
        f"/api/tasks/{task.id}",
        headers=headers,
    )
    assert response.status_code == 204, response.text

    assert not await row_exists(session, Task, task.id)
    assert not await row_exists(session, WeeklyTaskPlan, draft.id)
    assert not await row_exists(session, WeeklyTaskPlan, approved.id)
    assert (
        await session.scalar(
            select(func.count())
            .select_from(TaskAssignment)
            .where(TaskAssignment.task_id == task.id)
        )
    ) == 0
    assert await row_exists(session, Project, project.id)
    assert await row_exists(session, Employee, first.id)
    assert await row_exists(session, Employee, second.id)


async def test_task_delete_blocked_by_report(client, session):
    headers = await auth_headers(client)
    _, task = await make_project_and_task(session)
    plan = await make_plan(session, task)
    report = await make_update(
        session,
        message_id=5,
        task=task,
        plan=plan,
    )
    await session.commit()

    response = await client.delete(
        f"/api/tasks/{task.id}",
        headers=headers,
    )
    assert response.status_code == 409, response.text
    assert "1" in response.json()["detail"]
    assert await row_exists(session, Task, task.id)
    assert await row_exists(session, WeeklyTaskPlan, plan.id)
    assert await row_exists(session, TaskUpdate, report.id)


@pytest.mark.parametrize(
    "plan_status",
    ["draft", "approved", "rejected", "superseded"],
)
async def test_weekly_plan_status_can_be_deleted(
    client,
    session,
    plan_status,
):
    headers = await auth_headers(client)
    _, task = await make_project_and_task(session)
    plan = await make_plan(session, task, status=plan_status)
    await session.commit()

    response = await client.delete(
        f"/api/weekly-plans/{plan.id}",
        headers=headers,
    )
    assert response.status_code == 204, response.text
    assert not await row_exists(session, WeeklyTaskPlan, plan.id)


async def test_weekly_plan_used_by_report_cannot_be_deleted(
    client,
    session,
):
    headers = await auth_headers(client)
    _, task = await make_project_and_task(session)
    plan = await make_plan(session, task, status="approved")
    report = await make_update(
        session,
        message_id=6,
        plan=plan,
    )
    await session.commit()

    response = await client.delete(
        f"/api/weekly-plans/{plan.id}",
        headers=headers,
    )
    assert response.status_code == 409, response.text
    assert "1" in response.json()["detail"]
    assert await row_exists(session, WeeklyTaskPlan, plan.id)
    assert await row_exists(session, TaskUpdate, report.id)


async def test_pending_registration_request_can_be_deleted(
    client,
    session,
):
    headers = await auth_headers(client)
    request = RegistrationRequest(
        telegram_user_id=501,
        telegram_chat_id=501,
        requested_full_name="Bekleyen Aday",
        status="pending",
    )
    session.add(request)
    await session.commit()

    response = await client.delete(
        f"/api/registration-requests/{request.id}",
        headers=headers,
    )
    assert response.status_code == 204, response.text
    assert not await row_exists(session, RegistrationRequest, request.id)


async def test_approved_registration_request_delete_keeps_employee(
    client,
    session,
):
    headers = await auth_headers(client)
    employee = await make_employee(session, "Onaylı Çalışan")
    request = RegistrationRequest(
        telegram_user_id=502,
        telegram_chat_id=502,
        requested_full_name=employee.full_name,
        employee_id=employee.id,
        status="approved",
        reviewed_at=NOW,
    )
    session.add(request)
    await session.commit()

    response = await client.delete(
        f"/api/registration-requests/{request.id}",
        headers=headers,
    )
    assert response.status_code == 204, response.text
    assert not await row_exists(session, RegistrationRequest, request.id)
    assert await row_exists(session, Employee, employee.id)


async def test_rejected_registration_request_can_be_deleted(
    client,
    session,
):
    headers = await auth_headers(client)
    request = RegistrationRequest(
        telegram_user_id=503,
        telegram_chat_id=503,
        requested_full_name="Reddedilen Aday",
        status="rejected",
        reviewed_at=NOW,
    )
    session.add(request)
    await session.commit()

    response = await client.delete(
        f"/api/registration-requests/{request.id}",
        headers=headers,
    )
    assert response.status_code == 204, response.text
    assert not await row_exists(session, RegistrationRequest, request.id)


async def test_report_delete_keeps_task_plan_and_employee(client, session):
    headers = await auth_headers(client)
    employee = await make_employee(session, "Rapor Çalışanı")
    project, task = await make_project_and_task(
        session,
        employees=[employee],
    )
    plan = await make_plan(session, task, status="approved")
    report = await make_update(
        session,
        message_id=7,
        task=task,
        plan=plan,
        employee=employee,
    )
    await session.commit()

    response = await client.delete(
        f"/api/reports/{report.id}",
        headers=headers,
    )
    assert response.status_code == 204, response.text

    assert not await row_exists(session, TaskUpdate, report.id)
    assert await row_exists(session, Task, task.id)
    assert await row_exists(session, WeeklyTaskPlan, plan.id)
    assert await row_exists(session, Employee, employee.id)
    assert await row_exists(session, Project, project.id)

    listed = await client.get("/api/reports", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 0
    assert listed.json()["stats"]["total"] == 0


async def test_delete_missing_ids_return_404(client):
    headers = await auth_headers(client)
    endpoints = [
        "/api/projects/999999",
        "/api/employees/999999",
        "/api/tasks/999999",
        "/api/weekly-plans/999999",
        "/api/registration-requests/999999",
        "/api/reports/999999",
    ]

    for endpoint in endpoints:
        response = await client.delete(endpoint, headers=headers)
        assert response.status_code == 404, endpoint
