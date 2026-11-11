
import asyncio

from sqlalchemy import inspect

from app.database.connection import engine
from app.database.models import Base


async def main():
    try:
        print("Creating database tables...")

        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

            tables = await connection.run_sync(
                lambda conn: inspect(conn).get_table_names()
            )

        print("\nSUCCESS! Database schema initialized.")

        for table in tables:
            print(f"Table: {table}")

    except Exception as exc:
        print(f"Database initialization failed: {type(exc).__name__}")
        print(str(exc))

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())