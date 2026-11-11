
import os

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing from .env")


# Parse the Neon connection URL.
parsed_url = make_url(DATABASE_URL)

# Convert the URL to the asyncpg dialect.
# SSL is configured separately through connect_args.
query_params = {
    key: value
    for key, value in parsed_url.query.items()
    if key not in {"sslmode", "channel_binding"}
}

async_database_url = parsed_url.set(
    drivername="postgresql+asyncpg",
    query=query_params,
)


# Create the asynchronous database engine.
engine = create_async_engine(
    async_database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=1,
    max_overflow=0,
    connect_args={
        "ssl": True,
        "timeout": 15,
    },
)


# Session factory for database operations.
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def test_connection():

    async with engine.connect() as connection:

        result = await connection.execute(
            text("""
                SELECT
                    current_database() AS database_name,
                    current_user AS database_user,
                    version() AS server_version
            """)
        )

        return result.mappings().one()


async def close_database():
    await engine.dispose()