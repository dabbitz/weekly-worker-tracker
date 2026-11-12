from app.database.models import Employee
from tests.conftest import auth_headers


async def seed_employee(
    session,
    full_name: str,
    *,
    is_active: bool = True,
    telegram_user_id: int | None = None,
) -> int:
    employee = Employee(
        full_name=full_name,
        is_active=is_active,
        telegram_user_id=telegram_user_id,
    )
    session.add(employee)
    await session.commit()
    return employee.id


async def create_project(client, headers, name="Test Projesi") -> int:
    response = await client.post(
        "/api/projects",
        headers=headers,
        json={"name": name, "location": "Ankara"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_employee_list_and_detail_without_assignments(
    client,
    session,
):
    headers = await auth_headers(client)
    active_id = await seed_employee(session, "Zeynep Aktif")
    inactive_id = await seed_employee(session, "Ahmet Pasif", is_active=False)

    response = await client.get("/api/employees", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["items"][0]["id"] == active_id
    assert body["items"][0]["task_count"] == 0
    assert body["items"][0]["project_count"] == 0

    inactive_only = await client.get(
        "/api/employees",
        headers=headers,
        params={"is_active": "false"},
    )
    assert inactive_only.json()["total"] == 1
    assert inactive_only.json()["items"][0]["id"] == inactive_id

    detail = await client.get(
        f"/api/employees/{active_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["assigned_tasks"] == []
    assert detail_body["projects"] == []
    assert detail_body["task_count"] == 0


async def test_task_with_multiple_employees_and_derived_relations(
    client,
    session,
):
    headers = await auth_headers(client)
    first_id = await seed_employee(
        session,
        "Birinci Çalışan",
        telegram_user_id=111,
    )
    second_id = await seed_employee(
        session,
        "İkinci Çalışan",
        telegram_user_id=222,
    )
    project_id = await create_project(client, headers)

    create_response = await client.post(
        "/api/tasks",
        headers=headers,
        json={
            "project_id": project_id,
            "title": "Elektrik tesisatı",
            "description": "İkinci kat",
            "planned_start_date": "2026-11-09",
            "planned_due_date": "2026-11-13",
            "employee_ids": [first_id, second_id, first_id],
        },
    )
    assert create_response.status_code == 201, create_response.text
    task = create_response.json()
    assert task["project_name"] == "Test Projesi"
    assert len(task["assigned_employees"]) == 2
    assert task["planned_start_weekday"] == "pazartesi"
    assert task["planned_due_weekday"] == "cuma"

    task_id = task["id"]

    project_detail = await client.get(
        f"/api/projects/{project_id}",
        headers=headers,
    )
    assert project_detail.status_code == 200
    detail = project_detail.json()
    assert detail["task_count"] == 1
    assert detail["employee_count"] == 2
    assert {employee["id"] for employee in detail["employees"]} == {
        first_id,
        second_id,
    }
    assert len(detail["tasks"]) == 1
    assert len(detail["tasks"][0]["assigned_employees"]) == 2

    employees_endpoint = await client.get(
        f"/api/projects/{project_id}/employees",
        headers=headers,
    )
    assert employees_endpoint.status_code == 200
    assert len(employees_endpoint.json()) == 2

    employee_detail = await client.get(
        f"/api/employees/{first_id}",
        headers=headers,
    )
    assert employee_detail.status_code == 200
    employee_body = employee_detail.json()
    assert employee_body["task_count"] == 1
    assert employee_body["project_count"] == 1
    assert [project["id"] for project in employee_body["projects"]] == [
        project_id
    ]
    assert employee_body["assigned_tasks"][0]["id"] == task_id

    filtered_tasks = await client.get(
        "/api/tasks",
        headers=headers,
        params={"employee_id": second_id},
    )
    assert filtered_tasks.json()["total"] == 1

    update_response = await client.patch(
        f"/api/tasks/{task_id}",
        headers=headers,
        json={
            "title": "Elektrik tesisatı tamamlandı",
            "description": None,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == (
        "Elektrik tesisatı tamamlandı"
    )
    assert update_response.json()["description"] is None


async def test_assignment_replacement_and_inactive_rules(
    client,
    session,
):
    headers = await auth_headers(client)
    first_id = await seed_employee(session, "Aktif Bir")
    second_id = await seed_employee(session, "Aktif İki")
    inactive_id = await seed_employee(
        session,
        "Pasif Çalışan",
        is_active=False,
    )
    project_id = await create_project(client, headers)

    create_response = await client.post(
        "/api/tasks",
        headers=headers,
        json={
            "project_id": project_id,
            "title": "Boya işleri",
            "employee_ids": [first_id, second_id],
        },
    )
    task_id = create_response.json()["id"]

    replace = await client.put(
        f"/api/tasks/{task_id}/assignments",
        headers=headers,
        json={"employee_ids": [second_id, second_id]},
    )
    assert replace.status_code == 200
    assert [employee["id"] for employee in replace.json()["assigned_employees"]] == [
        second_id
    ]

    inactive_attempt = await client.put(
        f"/api/tasks/{task_id}/assignments",
        headers=headers,
        json={"employee_ids": [second_id, inactive_id]},
    )
    assert inactive_attempt.status_code == 422
    assert "Pasif" in inactive_attempt.json()["detail"]

    inactive_create = await client.post(
        "/api/tasks",
        headers=headers,
        json={
            "project_id": project_id,
            "title": "Pasif atama denemesi",
            "employee_ids": [inactive_id],
        },
    )
    assert inactive_create.status_code == 422

    missing_employee = await client.put(
        f"/api/tasks/{task_id}/assignments",
        headers=headers,
        json={"employee_ids": [999999]},
    )
    assert missing_employee.status_code == 422


async def test_existing_inactive_assignment_can_be_retained(
    client,
    session,
):
    headers = await auth_headers(client)
    employee_id = await seed_employee(session, "Sonradan Pasif")
    new_employee_id = await seed_employee(session, "Yeni Aktif")
    project_id = await create_project(client, headers)

    task_response = await client.post(
        "/api/tasks",
        headers=headers,
        json={
            "project_id": project_id,
            "title": "Kalıp işleri",
            "employee_ids": [employee_id],
        },
    )
    task_id = task_response.json()["id"]

    employee = await session.get(Employee, employee_id)
    employee.is_active = False
    await session.commit()

    response = await client.put(
        f"/api/tasks/{task_id}/assignments",
        headers=headers,
        json={"employee_ids": [employee_id, new_employee_id]},
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["assigned_employees"]) == 2


async def test_task_date_validation(client, session):
    headers = await auth_headers(client)
    project_id = await create_project(client, headers)

    response = await client.post(
        "/api/tasks",
        headers=headers,
        json={
            "project_id": project_id,
            "title": "Tarih hatalı görev",
            "planned_start_date": "2026-11-20",
            "planned_due_date": "2026-11-10",
        },
    )
    assert response.status_code == 422
    assert "başlangıç" in response.json()["detail"].lower()


async def test_task_requires_existing_project(client, session):
    headers = await auth_headers(client)
    response = await client.post(
        "/api/tasks",
        headers=headers,
        json={
            "project_id": 999999,
            "title": "Projesiz görev",
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Proje bulunamadı."
