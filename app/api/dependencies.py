import logging
from datetime import datetime, timezone
from typing import AsyncIterator

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.config import Settings, get_settings
from app.api.security import decode_access_token, is_token_revoked
from app.database.connection import SessionLocal


logger = logging.getLogger("worktrack.api")

_bearer_scheme = HTTPBearer(auto_error=False)


class AdminPrincipal:
    def __init__(
        self,
        username: str,
        jti: str,
        expires_at: datetime | None,
    ):
        self.username = username
        self.jti = jti
        self.expires_at = expires_at


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        _bearer_scheme
    ),
    settings: Settings = Depends(get_settings),
) -> AdminPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Oturum açmanız gerekiyor.")

    try:
        payload = decode_access_token(
            credentials.credentials,
            settings,
        )
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized(
            "Oturum süreniz doldu. Lütfen tekrar giriş yapın."
        ) from exc
    except jwt.PyJWTError as exc:
        raise _unauthorized("Geçersiz oturum bilgisi.") from exc

    jti = str(payload.get("jti", ""))

    if not jti or is_token_revoked(jti):
        raise _unauthorized("Oturum sonlandırılmış.")

    subject = str(payload.get("sub", ""))

    if subject != settings.admin_username:
        raise _unauthorized("Bu oturum için yetkiniz yok.")

    expires_at = datetime.fromtimestamp(
        int(payload["exp"]),
        tz=timezone.utc,
    )

    return AdminPrincipal(
        username=subject,
        jti=jti,
        expires_at=expires_at,
    )


require_admin = get_current_admin


def log_auth_failure() -> None:
    logger.warning("Admin authentication failed.")
