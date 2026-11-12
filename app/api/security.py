import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.api.config import Settings


ALGORITHM = "HS256"
TOKEN_TYPE = "worktrack_admin"

_password_hasher = PasswordHasher()

# In-memory logout denylist. This is appropriate for the single-process,
# single-administrator development setup. Restarting the API clears it.
_revoked_tokens: dict[str, int] = {}

# Simple in-memory login throttling.
_login_attempts: dict[str, list[float]] = {}
LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_ATTEMPTS = 8


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def create_access_token(
    username: str,
    settings: Settings,
) -> tuple[str, str, datetime]:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(
        minutes=settings.token_expire_minutes
    )
    jti = secrets.token_urlsafe(24)

    payload: dict[str, Any] = {
        "sub": username,
        "jti": jti,
        "type": TOKEN_TYPE,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    token = jwt.encode(
        payload,
        settings.auth_secret,
        algorithm=ALGORITHM,
    )

    return token, jti, expires_at


def decode_access_token(
    token: str,
    settings: Settings,
) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        settings.auth_secret,
        algorithms=[ALGORITHM],
        options={"require": ["sub", "exp", "iat", "jti", "type"]},
    )

    if payload.get("type") != TOKEN_TYPE:
        raise jwt.InvalidTokenError("Geçersiz token türü.")

    return payload


def revoke_token(jti: str, expires_at: datetime | None) -> None:
    expiry = (
        int(expires_at.timestamp())
        if expires_at is not None
        else int(time.time()) + 3600
    )
    _revoked_tokens[jti] = expiry
    _prune_revoked_tokens()


def is_token_revoked(jti: str) -> bool:
    _prune_revoked_tokens()
    return jti in _revoked_tokens


def _prune_revoked_tokens() -> None:
    now = int(time.time())
    expired = [
        token_id
        for token_id, expiry in _revoked_tokens.items()
        if expiry <= now
    ]
    for token_id in expired:
        _revoked_tokens.pop(token_id, None)


def is_login_rate_limited(key: str) -> bool:
    now = time.time()
    attempts = [
        attempt
        for attempt in _login_attempts.get(key, [])
        if now - attempt < LOGIN_WINDOW_SECONDS
    ]
    _login_attempts[key] = attempts
    return len(attempts) >= LOGIN_MAX_ATTEMPTS


def record_failed_login(key: str) -> None:
    _login_attempts.setdefault(key, []).append(time.time())


def clear_login_attempts(key: str) -> None:
    _login_attempts.pop(key, None)


def reset_security_state() -> None:
    """Used by the automated test suite."""

    _revoked_tokens.clear()
    _login_attempts.clear()
