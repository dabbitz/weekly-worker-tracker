from datetime import datetime, timezone

from sqlalchemy import func, select

from app.database.models import Employee, RegistrationRequest
from app.services import employee_service
from tests.conftest import auth_headers
from tests.test_employees_tasks import seed_employee


async def seed_registration_request(
    session,
    *,
    telegram_user_id: int,
    full_name: str,
    role: str | None = None,
    status: str = "pending",
) -> int:
    request = RegistrationRequest(
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_user_id,
        requested_full_name=full_name,
        requested_role=role,
        status=status,
        reviewed_at=(
            datetime.now(timezone.utc)
            if status in ("approved", "rejected")
            else None
        ),
        reviewed_by_telegram_user_id=(
            999000111
            if status in ("approved", "rejected")
            else None
        ),
    )
    session.add(request)
    await session.commit()
    return request.id


async def test_registration_requests_are_listed_and_filtered(
    client,
    session,
):
    headers = await auth_headers(client)
    await seed_registration_request(
        session,
        telegram_user_id=101,
        full_name="Bekleyen Başvuru",
    )
    await seed_registration_request(
        session,
        telegram_user_id=102,
        full_name="Onaylanan Başvuru",
        status="approved",
    )

    all_requests = await client.get(
        "/api/registration-requests",
        headers=headers,
    )
    assert all_requests.status_code == 200
    assert all_requests.json()["total"] == 2

    pending = await client.get(
        "/api/registration-requests",
        headers=headers,
        params={"status": "pending"},
    )
    assert pending.json()["total"] == 1
    assert pending.json()["items"][0]["requested_full_name"] == (
        "Bekleyen Başvuru"
    )

    search = await client.get(
        "/api/registration-requests",
        headers=headers,
        params={"search": "Onaylanan"},
    )
    assert search.json()["total"] == 1


async def test_telegram_approval_flow_still_creates_employee(
    client,
    session,
):
    request_id = await seed_registration_request(
        session,
        telegram_user_id=555,
        full_name="Yeni Çalışan",
    )

    request, employee, state = await (
        employee_service.review_registration_request(
            request_id=request_id,
            admin_telegram_user_id=999000111,
            approve=True,
        )
    )

    assert state == "approved"
    assert request.status == "approved"
    assert employee is not None
    assert employee.is_active is True
    assert employee.full_name == "Yeni Çalışan"

    stored_employee = await session.get(Employee, employee.id)
    assert stored_employee is not None
    assert stored_employee.telegram_user_id == 555

    second_attempt = await employee_service.review_registration_request(
        request_id=request_id,
        admin_telegram_user_id=999000111,
        approve=True,
    )
    assert second_attempt[2] == "already_reviewed"


async def test_telegram_rejection_does_not_create_employee(
    client,
    session,
):
    request_id = await seed_registration_request(
        session,
        telegram_user_id=777,
        full_name="Reddedilecek Kişi",
    )

    request, employee, state = await (
        employee_service.review_registration_request(
            request_id=request_id,
            admin_telegram_user_id=999000111,
            approve=False,
        )
    )

    assert state == "rejected"
    assert request.status == "rejected"
    assert employee is None

    employee_count = await session.execute(
        select(func.count(Employee.id)).where(
            Employee.telegram_user_id == 777
        )
    )
    assert employee_count.scalar_one() == 0


async def test_missing_registration_request(client, session):
    request, employee, state = await (
        employee_service.review_registration_request(
            request_id=999999,
            admin_telegram_user_id=999000111,
            approve=True,
        )
    )
    assert request is None
    assert employee is None
    assert state == "not_found"


async def test_registration_position_is_stored_and_copied_on_approval(
    client,
    session,
):
    request, state = await employee_service.create_registration_request(
        telegram_user_id=901,
        telegram_chat_id=901,
        full_name="Pozisyonlu Çalışan",
        role="Elektrik Mühendisi",
    )

    assert state == "created"
    assert request is not None
    assert request.requested_role == "Elektrik Mühendisi"

    headers = await auth_headers(client)
    listed = await client.get(
        "/api/registration-requests",
        headers=headers,
        params={"status": "pending"},
    )
    assert listed.status_code == 200
    assert listed.json()["items"][0]["requested_role"] == (
        "Elektrik Mühendisi"
    )

    reviewed_request, employee, review_state = await (
        employee_service.review_registration_request(
            request_id=request.id,
            admin_telegram_user_id=999000111,
            approve=True,
        )
    )

    assert review_state == "approved"
    assert reviewed_request.status == "approved"
    assert employee is not None
    assert employee.full_name == "Pozisyonlu Çalışan"
    assert employee.role == "Elektrik Mühendisi"

    stored_employee = await session.get(Employee, employee.id)
    assert stored_employee is not None
    assert stored_employee.role == "Elektrik Mühendisi"


async def test_registration_without_position_can_be_filled_later_by_admin(
    client,
    session,
):
    request, state = await employee_service.create_registration_request(
        telegram_user_id=902,
        telegram_chat_id=902,
        full_name="Pozisyonsuz Çalışan",
        role=None,
    )
    assert state == "created"
    assert request is not None
    assert request.requested_role is None

    _request, employee, review_state = await (
        employee_service.review_registration_request(
            request_id=request.id,
            admin_telegram_user_id=999000111,
            approve=True,
        )
    )
    assert review_state == "approved"
    assert employee is not None
    assert employee.role is None

    headers = await auth_headers(client)
    response = await client.patch(
        f"/api/employees/{employee.id}",
        headers=headers,
        json={"role": "Proje Yöneticisi"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "Proje Yöneticisi"


async def test_admin_updates_and_clears_employee_position(
    client,
    session,
):
    headers = await auth_headers(client)
    employee_id = await seed_employee(session, "Pozisyon Testi")

    updated = await client.patch(
        f"/api/employees/{employee_id}",
        headers=headers,
        json={"role": "  Yazılım   Mühendisi  "},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["role"] == "Yazılım Mühendisi"

    detail = await client.get(
        f"/api/employees/{employee_id}",
        headers=headers,
    )
    assert detail.json()["role"] == "Yazılım Mühendisi"

    too_long = await client.patch(
        f"/api/employees/{employee_id}",
        headers=headers,
        json={"role": "a" * 81},
    )
    assert too_long.status_code == 422

    cleared = await client.patch(
        f"/api/employees/{employee_id}",
        headers=headers,
        json={"role": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["role"] is None

    missing = await client.patch(
        "/api/employees/999999",
        headers=headers,
        json={"role": "Teknisyen"},
    )
    assert missing.status_code == 404
