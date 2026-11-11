
import asyncio

from app.database.connection import (
    engine,
    test_connection,
)


async def main():

    try:
        print("Connecting to Neon PostgreSQL...\n")

        database_info = await test_connection()

        print("SUCCESS! Database connection established.")
        print("------------------------------------------")

        print(
            f"Database: {database_info['database_name']}"
        )

        print(
            f"User: {database_info['database_user']}"
        )

        print(
            f"Server: {database_info['server_version'].split(',')[0]}"
        )

    except Exception as exc:

        print(f"Database connection failed: {type(exc).__name__}")
        print(str(exc))

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())