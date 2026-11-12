from datetime import datetime, timezone

from sqlalchemy import func, select

from app.database.models import Employee, RegistrationRequest
from app.services import employee_service
from tests.conftest import auth_headers


async def seed_registration_request(
    session,
    *,
    telegram_user_id: int,
    full_name: str,
    status: str = "pending",
) -> int:
    request = RegistrationRequest(
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_user_id,
        requested_full_name=full_name,
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
