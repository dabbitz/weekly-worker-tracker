from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Employee, RegistrationRequest
from app.schemas.common import Page
from app.schemas.registration import RegistrationRequestRead
from app.services.exceptions import NotFoundError


def _to_read(
    request: RegistrationRequest,
    employee_full_name: str | None,
) -> RegistrationRequestRead:
    return RegistrationRequestRead(
        id=request.id,
        telegram_user_id=request.telegram_user_id,
        requested_full_name=request.requested_full_name,
        requested_role=request.requested_role,
        employee_id=request.employee_id,
        employee_full_name=employee_full_name,
        status=request.status,
        created_at=request.created_at,
        notification_sent_at=request.notification_sent_at,
        reviewed_at=request.reviewed_at,
        reviewed_by_telegram_user_id=(
            request.reviewed_by_telegram_user_id
        ),
    )


async def list_registration_requests(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    status_filter: str | None = None,
    search: str | None = None,
) -> Page[RegistrationRequestRead]:
    filters = []

    if status_filter:
        filters.append(RegistrationRequest.status == status_filter)

    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            RegistrationRequest.requested_full_name.ilike(pattern)
        )

    total = int(
        (
            await session.execute(
                select(func.count(RegistrationRequest.id)).where(
                    *filters
                )
            )
        ).scalar_one()
    )

    rows = (
        await session.execute(
            select(
                RegistrationRequest,
                Employee.full_name.label("employee_full_name"),
            )
            .outerjoin(
                Employee,
                Employee.id == RegistrationRequest.employee_id,
            )
            .where(*filters)
            .order_by(
                RegistrationRequest.created_at.desc(),
                RegistrationRequest.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items = [
        _to_read(request, employee_full_name)
        for request, employee_full_name in rows
    ]

    return Page[RegistrationRequestRead](
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
    )


async def review_registration_request_in_session(
    session: AsyncSession,
    request_id: int,
    approve: bool,
    reviewer_telegram_user_id: int | None,
):
    """Shared review logic used by the Telegram callback and tests.

    The Telegram handler keeps its own authorization checks. This function
    only performs the database transition and never trusts a caller-supplied
    employee ID.
    """

    result = await session.execute(
        select(RegistrationRequest)
        .where(RegistrationRequest.id == request_id)
        .with_for_update()
    )

    request = result.scalar_one_or_none()

    if request is None:
        return None, None, "not_found"

    if request.status != "pending":
        return request, None, "already_reviewed"

    employee = None

    if approve:
        if request.employee_id is not None:
            employee = await session.get(Employee, request.employee_id)

        if employee is None:
            employee_result = await session.execute(
                select(Employee).where(
                    Employee.telegram_user_id == request.telegram_user_id
                )
            )
            employee = employee_result.scalar_one_or_none()

        if employee is None:
            employee = Employee(
                telegram_user_id=request.telegram_user_id,
                full_name=request.requested_full_name,
                role=request.requested_role,
            )
            session.add(employee)
        else:
            employee.full_name = request.requested_full_name
            employee.is_active = True

            # The position reported with the request wins only when it was
            # actually provided; an empty value never wipes a position the
            # administrator already entered.
            if request.requested_role:
                employee.role = request.requested_role

        await session.flush()

        request.employee_id = employee.id
        request.status = "approved"
    else:
        request.status = "rejected"

    request.reviewed_at = datetime.now(timezone.utc)
    request.reviewed_by_telegram_user_id = reviewer_telegram_user_id

    await session.commit()

    if employee is not None:
        await session.refresh(employee)

    await session.refresh(request)

    return request, employee, "approved" if approve else "rejected"


async def get_registration_request(
    session: AsyncSession,
    request_id: int,
) -> RegistrationRequestRead:
    row = (
        await session.execute(
            select(
                RegistrationRequest,
                Employee.full_name.label("employee_full_name"),
            )
            .outerjoin(
                Employee,
                Employee.id == RegistrationRequest.employee_id,
            )
            .where(RegistrationRequest.id == request_id)
        )
    ).one_or_none()

    if row is None:
        raise NotFoundError("Kayıt talebi bulunamadı.")

    request, employee_full_name = row
    return _to_read(request, employee_full_name)


async def delete_registration_request(
    session: AsyncSession,
    request_id: int,
) -> None:
    """Delete a registration request in any review state.

    The request is the only record removed. In particular, deleting an
    approved request never deletes the employee created by that approval.
    """

    request = await session.get(RegistrationRequest, request_id)

    if request is None:
        raise NotFoundError("Kayıt talebi bulunamadı.")

    await session.delete(request)
    await session.commit()
