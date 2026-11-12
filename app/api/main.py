import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.config import ConfigurationError, get_settings
from app.api.errors import register_error_handlers
from app.api.routes import (
    auth,
    dashboard,
    employees,
    health,
    projects,
    registration_requests,
    tasks,
    weekly_plans,
)
from app.database.connection import close_database


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("worktrack.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        settings = get_settings()
    except ConfigurationError as exc:
        logger.error("WorkTrack API configuration error: %s", exc)
        raise

    logger.info(
        "WorkTrack API started. Allowed frontend origins: %s",
        ", ".join(settings.frontend_origins),
    )

    try:
        yield
    finally:
        await close_database()
        logger.info("WorkTrack API database connections closed.")


app = FastAPI(
    title="WorkTrack Yönetim API",
    description=(
        "WorkTrack yönetici paneli için kimlik doğrulamalı REST API. "
        "Telegram botundan bağımsız bir süreç olarak çalışır."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

settings_for_import = None

try:
    settings_for_import = get_settings()
except ConfigurationError:
    # Import stays side-effect free so tooling and tests can import the app
    # before configuring environment variables. Startup still validates.
    settings_for_import = None

_allowed_origins = (
    settings_for_import.frontend_origins
    if settings_for_import is not None
    else ("http://localhost:5173", "http://127.0.0.1:5173")
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

register_error_handlers(app)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(employees.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(weekly_plans.router, prefix="/api")
app.include_router(registration_requests.router, prefix="/api")


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "WorkTrack Yönetim API",
        "health": "/api/health",
        "docs": "/docs",
    }
