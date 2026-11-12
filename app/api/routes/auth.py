from secrets import compare_digest

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.config import Settings, get_settings
from app.api.dependencies import AdminPrincipal, require_admin
from app.api.security import (
    clear_login_attempts,
    create_access_token,
    is_login_rate_limited,
    record_failed_login,
    revoke_token,
    verify_password,
)
from app.schemas.auth import AdminRead, LoginRequest, TokenResponse


router = APIRouter(prefix="/auth", tags=["auth"])


def _client_key(request: Request) -> str:
    if request.client is None:
        return "unknown"
    return request.client.host


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    key = _client_key(request)

    if is_login_rate_limited(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Çok fazla başarısız giriş denemesi. "
                "Lütfen birkaç dakika sonra tekrar deneyin."
            ),
        )

    username_matches = compare_digest(
        payload.username,
        settings.admin_username,
    )
    password_matches = verify_password(
        payload.password,
        settings.admin_password_hash,
    )

    if not (username_matches and password_matches):
        record_failed_login(key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı adı veya parola hatalı.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    clear_login_attempts(key)

    token, _jti, expires_at = create_access_token(
        settings.admin_username,
        settings,
    )

    return TokenResponse(
        access_token=token,
        expires_at=expires_at,
        admin=AdminRead(username=settings.admin_username),
    )


@router.get("/me", response_model=AdminRead)
async def current_admin(
    admin: AdminPrincipal = Depends(require_admin),
) -> AdminRead:
    return AdminRead(username=admin.username)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    admin: AdminPrincipal = Depends(require_admin),
) -> None:
    revoke_token(admin.jti, admin.expires_at)
