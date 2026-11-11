
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database.connection import SessionLocal
from app.database.models import Employee, RegistrationRequest


async def create_registration_request(
    telegram_user_id: int,
    telegram_chat_id: int,
    full_name: str,
) -> tuple[RegistrationRequest | None, str]:

    async with SessionLocal() as session:

        # Check whether this Telegram account
        # already has an employee record.

        employee_result = await session.execute(
            select(Employee).where(
                Employee.telegram_user_id == telegram_user_id
            )
        )

        employee = employee_result.scalar_one_or_none()

        if employee is not None and employee.is_active:
            return None, "already_registered"

        # Check for an existing pending request.

        pending_result = await session.execute(
            select(RegistrationRequest).where(
                RegistrationRequest.telegram_user_id == telegram_user_id,
                RegistrationRequest.status == "pending",
            )
        )

        existing_request = pending_result.scalar_one_or_none()

        if existing_request is not None:
            return existing_request, "pending"

        # Create a pending request.
        # No Employee record is created at this stage.

        request = RegistrationRequest(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            requested_full_name=full_name,
            employee_id=employee.id if employee else None,
        )

        session.add(request)

        try:
            await session.commit()
            await session.refresh(request)

            return request, "created"

        except IntegrityError:

            await session.rollback()

            # Handle simultaneous requests from the same account.

            result = await session.execute(
                select(RegistrationRequest).where(
                    RegistrationRequest.telegram_user_id == telegram_user_id,
                    RegistrationRequest.status == "pending",
                )
            )

            existing_request = result.scalar_one_or_none()

            if existing_request is not None:
                return existing_request, "pending"

            raise


async def mark_registration_notified(request_id: int):

    async with SessionLocal() as session:

        request = await session.get(
            RegistrationRequest,
            request_id
        )

        if request is None or request.status != "pending":
            return

        request.notification_sent_at = datetime.now(timezone.utc)

        await session.commit()


async def review_registration_request(
    request_id: int,
    admin_telegram_user_id: int,
    approve: bool,
):

    async with SessionLocal() as session:

        result = await session.execute(
            select(RegistrationRequest)
            .where(RegistrationRequest.id == request_id)
            .with_for_update()
        )

        request = result.scalar_one_or_none()

        if request is None:
            return None, None, "not_found"

        # A request must only be reviewed once.

        if request.status != "pending":
            return request, None, "already_reviewed"

        employee = None

        if approve:

            # Reactivate an existing employee if this
            # is a reactivation request.

            if request.employee_id is not None:

                employee = await session.get(
                    Employee,
                    request.employee_id
                )

            # Otherwise, look up the Telegram account.

            if employee is None:

                employee_result = await session.execute(
                    select(Employee).where(
                        Employee.telegram_user_id
                        == request.telegram_user_id
                    )
                )

                employee = employee_result.scalar_one_or_none()

            # Create a new employee if no account exists.

            if employee is None:

                employee = Employee(
                    telegram_user_id=request.telegram_user_id,
                    full_name=request.requested_full_name,
                )

                session.add(employee)

            else:

                employee.full_name = request.requested_full_name
                employee.is_active = True

            await session.flush()

            request.employee_id = employee.id
            request.status = "approved"

        else:

            request.status = "rejected"

        request.reviewed_at = datetime.now(timezone.utc)

        request.reviewed_by_telegram_user_id = (
            admin_telegram_user_id
        )

        await session.commit()

        await session.refresh(request)

        if employee is not None:
            await session.refresh(employee)

        return (
            request,
            employee,
            "approved" if approve else "rejected"
        )