import pytest

from tests.conftest import auth_headers, login


@pytest.mark.parametrize(
    "path",
    [
        "/api/dashboard/summary",
        "/api/projects",
        "/api/projects/options",
        "/api/employees",
        "/api/tasks",
        "/api/weekly-plans",
        "/api/registration-requests",
    ],
)
async def test_admin_endpoints_require_authentication(client, path):
    response = await client.get(path)
    assert response.status_code == 401


async def test_health_is_public(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_login_rejects_wrong_password(client):
    response = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert "hatalı" in response.json()["detail"].lower()


async def test_login_success_me_and_logout(client):
    headers = await auth_headers(client)

    me_response = await client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "admin"

    logout_response = await client.post(
        "/api/auth/logout",
        headers=headers,
    )
    assert logout_response.status_code == 204

    me_after_logout = await client.get("/api/auth/me", headers=headers)
    assert me_after_logout.status_code == 401


async def test_invalid_bearer_token_is_rejected(client):
    response = await client.get(
        "/api/projects",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


async def test_login_response_never_contains_secret_fields(client):
    response = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test-password-123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    serialized = str(body).lower()
    assert "database_url" not in serialized
    assert "password_hash" not in serialized
    assert "bot_token" not in serialized


async def test_two_logins_both_work(client):
    first = await login(client)
    second = await login(client)
    assert first != second
    for token in (first, second):
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
