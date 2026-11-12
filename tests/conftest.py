import os
import uuid
from dataclasses import dataclass

import pytest
import pytest_asyncio
from argon2 import PasswordHasher
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault(
    "ADMIN_PASSWORD_HASH",
    PasswordHasher().hash("test-password-123"),
)
os.environ.setdefault(
    "AUTH_SECRET",
    "test-only-secret-0123456789abcdef0123456789",
)
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("ADMIN_TELEGRAM_ID", "999000111")


from app.api.dependencies import get_db  # noqa: E402
from app.api.main import app  # noqa: E402
from app.api.security import reset_security_state  # noqa: E402
from app.database.connection import async_database_url  # noqa: E402
from app.database.models import Base  # noqa: E402


ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = "test-password-123"


@dataclass
class TestDatabase:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    schema: str


@pytest_asyncio.fixture
async def database(monkeypatch) -> TestDatabase:
    schema = f"worktrack_test_{uuid.uuid4().hex[:10]}"

    admin_engine = create_async_engine(
        async_database_url,
        pool_pre_ping=True,
        connect_args={"ssl": True, "timeout": 20},
    )

    async with admin_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    test_engine = create_async_engine(
        async_database_url,
        pool_pre_ping=True,
        connect_args={"ssl": True, "timeout": 20},
    )

    # asyncpg ignores server_settings.search_path with Neon here, so apply
    # the schema explicitly on every new pooled connection. This keeps tests
    # fully isolated from the persistent public schema.
    @event.listens_for(test_engine.sync_engine, "connect")
    def _set_test_search_path(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute(f'SET search_path TO "{schema}"')
        cursor.close()

    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    monkeypatch.setattr(
        "app.services.employee_service.SessionLocal",
        sessionmaker,
    )

    reset_security_state()

    database = TestDatabase(
        engine=test_engine,
        sessionmaker=sessionmaker,
        schema=schema,
    )

    try:
        yield database
    finally:
        await test_engine.dispose()

        async with admin_engine.begin() as connection:
            await connection.execute(
                text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            )

        await admin_engine.dispose()


@pytest_asyncio.fixture
async def session(database: TestDatabase):
    async with database.sessionmaker() as db_session:
        yield db_session


@pytest_asyncio.fixture
async def client(database: TestDatabase):
    async def override_get_db():
        async with database.sessionmaker() as db_session:
            yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as http_client:
        yield http_client

    app.dependency_overrides.clear()


async def login(client: AsyncClient) -> str:
    response = await client.post(
        "/api/auth/login",
        json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def auth_headers(client: AsyncClient) -> dict[str, str]:
    token = await login(client)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def credentials() -> tuple[str, str]:
    return ADMIN_USERNAME, ADMIN_PASSWORD
