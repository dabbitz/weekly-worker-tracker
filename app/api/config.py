import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


DEFAULT_FRONTEND_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


class ConfigurationError(RuntimeError):
    """Raised when the dashboard backend is not configured safely."""


@dataclass(frozen=True)
class Settings:
    admin_username: str
    admin_password_hash: str
    auth_secret: str
    token_expire_minutes: int
    frontend_origins: tuple[str, ...]
    admin_telegram_id: int | None


def _parse_optional_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        return int(value)
    except ValueError:
        return None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load dashboard settings without ever logging their values."""

    missing = [
        name
        for name in (
            "ADMIN_USERNAME",
            "ADMIN_PASSWORD_HASH",
            "AUTH_SECRET",
        )
        if not os.getenv(name)
    ]

    if missing:
        raise ConfigurationError(
            "Missing dashboard environment variables: "
            + ", ".join(missing)
            + ". See .env.example."
        )

    auth_secret = os.environ["AUTH_SECRET"]

    if len(auth_secret) < 32:
        raise ConfigurationError(
            "AUTH_SECRET must be at least 32 characters long."
        )

    raw_expire = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480")

    try:
        token_expire_minutes = int(raw_expire)
    except ValueError as exc:
        raise ConfigurationError(
            "ACCESS_TOKEN_EXPIRE_MINUTES must be an integer."
        ) from exc

    if token_expire_minutes < 5 or token_expire_minutes > 10080:
        raise ConfigurationError(
            "ACCESS_TOKEN_EXPIRE_MINUTES must be between 5 and 10080."
        )

    extra_origin = os.getenv("FRONTEND_ORIGIN", "").strip()
    origins = list(DEFAULT_FRONTEND_ORIGINS)

    if extra_origin and extra_origin not in origins:
        origins.append(extra_origin)

    return Settings(
        admin_username=os.environ["ADMIN_USERNAME"],
        admin_password_hash=os.environ["ADMIN_PASSWORD_HASH"],
        auth_secret=auth_secret,
        token_expire_minutes=token_expire_minutes,
        frontend_origins=tuple(origins),
        admin_telegram_id=_parse_optional_int(
            os.getenv("ADMIN_TELEGRAM_ID")
        ),
    )
