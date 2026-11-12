from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, require_admin
from app.schemas.common import Page
from app.schemas.registration import RegistrationRequestRead
from app.services import registration_service


router = APIRouter(
    prefix="/registration-requests",
    tags=["registration-requests"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=Page[RegistrationRequestRead])
async def list_requests(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        pattern="^(pending|approved|rejected)$",
    ),
    search: str | None = Query(default=None, max_length=200),
    session: AsyncSession = Depends(get_db),
) -> Page[RegistrationRequestRead]:
    return await registration_service.list_registration_requests(
        session,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        search=search,
    )


@router.get(
    "/{request_id}",
    response_model=RegistrationRequestRead,
)
async def request_detail(
    request_id: int,
    session: AsyncSession = Depends(get_db),
) -> RegistrationRequestRead:
    return await registration_service.get_registration_request(
        session,
        request_id,
    )
