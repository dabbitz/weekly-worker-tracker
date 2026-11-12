from tests.conftest import auth_headers


async def test_project_create_list_detail_and_update(client):
    headers = await auth_headers(client)

    create_response = await client.post(
        "/api/projects",
        headers=headers,
        json={
            "name": "  Merkez Ofis Yenileme  ",
            "description": "İkinci kat renovasyonu",
            "location": "İstanbul",
            "expected_completion_date": "2026-12-31",
        },
    )
    assert create_response.status_code == 201, create_response.text
    project = create_response.json()
    assert project["name"] == "Merkez Ofis Yenileme"
    assert project["task_count"] == 0
    assert project["employee_count"] == 0

    list_response = await client.get(
        "/api/projects",
        headers=headers,
    )
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] == 1
    assert body["pages"] == 1
    assert body["items"][0]["id"] == project["id"]

    search_response = await client.get(
        "/api/projects",
        headers=headers,
        params={"search": "istanbul"},
    )
    assert search_response.json()["total"] == 1

    empty_search = await client.get(
        "/api/projects",
        headers=headers,
        params={"search": "bulunmayan"},
    )
    assert empty_search.json()["total"] == 0

    detail_response = await client.get(
        f"/api/projects/{project['id']}",
        headers=headers,
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["tasks"] == []
    assert detail["employees"] == []

    update_response = await client.patch(
        f"/api/projects/{project['id']}",
        headers=headers,
        json={
            "name": "Merkez Ofis Yenileme Faz 2",
            "expected_completion_date": None,
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "Merkez Ofis Yenileme Faz 2"
    assert updated["expected_completion_date"] is None


async def test_project_name_cannot_be_blank(client):
    headers = await auth_headers(client)
    response = await client.post(
        "/api/projects",
        headers=headers,
        json={"name": "   "},
    )
    assert response.status_code == 422
    assert "boş" in response.json()["detail"]


async def test_missing_project_returns_404(client):
    headers = await auth_headers(client)
    response = await client.get("/api/projects/999999", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Proje bulunamadı."


async def test_project_options_are_real_projects(client):
    headers = await auth_headers(client)

    for name in ("Beta Projesi", "Alfa Projesi"):
        response = await client.post(
            "/api/projects",
            headers=headers,
            json={"name": name},
        )
        assert response.status_code == 201

    options = await client.get("/api/projects/options", headers=headers)
    assert options.status_code == 200
    names = [option["name"] for option in options.json()]
    assert names == ["Alfa Projesi", "Beta Projesi"]
