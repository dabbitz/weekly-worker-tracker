
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database.connection import SessionLocal
from app.database.models import Employee, RegistrationRequest
from app.services.registration_service import (
    review_registration_request_in_session,
)


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

        return await review_registration_request_in_session(
            session=session,
            request_id=request_id,
            approve=approve,
            reviewer_telegram_user_id=admin_telegram_user_id,
        )
