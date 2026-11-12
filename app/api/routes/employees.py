from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, require_admin
from app.schemas.common import Page
from app.schemas.employee import EmployeeRead
from app.schemas.employee_detail import EmployeeDetail
from app.services import employee_query_service


router = APIRouter(
    prefix="/employees",
    tags=["employees"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=Page[EmployeeRead])
async def list_employees(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    is_active: bool | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> Page[EmployeeRead]:
    return await employee_query_service.list_employees(
        session,
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
    )


@router.get("/{employee_id}", response_model=EmployeeDetail)
async def employee_detail(
    employee_id: int,
    session: AsyncSession = Depends(get_db),
) -> EmployeeDetail:
    return await employee_query_service.get_employee_detail(
        session,
        employee_id,
    )
