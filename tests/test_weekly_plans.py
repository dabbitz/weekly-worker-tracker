from tests.conftest import auth_headers


async def create_project_and_task(client, headers) -> tuple[int, int]:
    project_response = await client.post(
        "/api/projects",
        headers=headers,
        json={"name": "Plan Projesi"},
    )
    project_id = project_response.json()["id"]

    task_response = await client.post(
        "/api/tasks",
        headers=headers,
        json={
            "project_id": project_id,
            "title": "Planlanacak görev",
        },
    )
    assert task_response.status_code == 201, task_response.text
    return project_id, task_response.json()["id"]


async def test_weekly_plan_create_update_list_and_duplicate(
    client,
):
    headers = await auth_headers(client)
    project_id, task_id = await create_project_and_task(client, headers)

    create_response = await client.post(
        "/api/weekly-plans",
        headers=headers,
        json={
            "task_id": task_id,
            "week_start_date": "2026-11-09",
            "week_end_date": "2026-11-15",
            "target_description": "Tesisatın %40'ını bitir",
            "target_completion_percentage": 40,
        },
    )
    assert create_response.status_code == 201, create_response.text
    plan = create_response.json()
    assert plan["task_title"] == "Planlanacak görev"
    assert plan["project_id"] == project_id
    assert plan["target_completion_percentage"] == 40

    duplicate = await client.post(
        "/api/weekly-plans",
        headers=headers,
        json={
            "task_id": task_id,
            "week_start_date": "2026-11-09",
            "week_end_date": "2026-11-15",
            "target_description": "Tekrar",
            "target_completion_percentage": 50,
        },
    )
    assert duplicate.status_code == 409

    list_response = await client.get(
        "/api/weekly-plans",
        headers=headers,
        params={"project_id": project_id},
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    by_task = await client.get(
        "/api/weekly-plans",
        headers=headers,
        params={"task_id": task_id},
    )
    assert by_task.json()["total"] == 1

    update_response = await client.patch(
        f"/api/weekly-plans/{plan['id']}",
        headers=headers,
        json={
            "target_completion_percentage": 75,
            "target_description": "Tesisatın %75'ini bitir",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["target_completion_percentage"] == 75

    detail = await client.get(
        f"/api/weekly-plans/{plan['id']}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["target_description"] == (
        "Tesisatın %75'ini bitir"
    )


async def test_weekly_plan_date_and_percentage_validation(client):
    headers = await auth_headers(client)
    _, task_id = await create_project_and_task(client, headers)

    inverted_dates = await client.post(
        "/api/weekly-plans",
        headers=headers,
        json={
            "task_id": task_id,
            "week_start_date": "2026-11-15",
            "week_end_date": "2026-11-09",
            "target_description": "Hatalı hafta",
            "target_completion_percentage": 30,
        },
    )
    assert inverted_dates.status_code == 422

    invalid_percentage = await client.post(
        "/api/weekly-plans",
        headers=headers,
        json={
            "task_id": task_id,
            "week_start_date": "2026-11-09",
            "week_end_date": "2026-11-15",
            "target_description": "Hatalı yüzde",
            "target_completion_percentage": 140,
        },
    )
    assert invalid_percentage.status_code == 422

    missing_task = await client.post(
        "/api/weekly-plans",
        headers=headers,
        json={
            "task_id": 999999,
            "week_start_date": "2026-11-09",
            "week_end_date": "2026-11-15",
            "target_description": "Görev yok",
            "target_completion_percentage": 10,
        },
    )
    assert missing_task.status_code == 404


async def test_plan_task_can_move_to_another_task(client):
    headers = await auth_headers(client)
    project_id, first_task_id = await create_project_and_task(
        client,
        headers,
    )
    second_task = await client.post(
        "/api/tasks",
        headers=headers,
        json={
            "project_id": project_id,
            "title": "İkinci plan görevi",
        },
    )
    second_task_id = second_task.json()["id"]

    plan = await client.post(
        "/api/weekly-plans",
        headers=headers,
        json={
            "task_id": first_task_id,
            "week_start_date": "2026-11-09",
            "week_end_date": "2026-11-15",
            "target_description": "İlk hedef",
            "target_completion_percentage": 20,
        },
    )
    plan_id = plan.json()["id"]

    updated = await client.patch(
        f"/api/weekly-plans/{plan_id}",
        headers=headers,
        json={"task_id": second_task_id},
    )
    assert updated.status_code == 200
    assert updated.json()["task_id"] == second_task_id
