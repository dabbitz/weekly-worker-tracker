from datetime import datetime

from pydantic import BaseModel


class RegistrationRequestRead(BaseModel):
    id: int
    telegram_user_id: int
    requested_full_name: str
    requested_role: str | None = None
    employee_id: int | None
    employee_full_name: str | None = None
    status: str
    created_at: datetime
    notification_sent_at: datetime | None
    reviewed_at: datetime | None
    reviewed_by_telegram_user_id: int | None
