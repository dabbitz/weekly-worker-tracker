import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.services.exceptions import ServiceError


logger = logging.getLogger("worktrack.api")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def service_error_handler(
        request: Request,
        exc: ServiceError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = []

        for error in exc.errors():
            location = ".".join(
                str(part)
                for part in error.get("loc", ())
                if part not in ("body", "query", "path")
            )
            errors.append(
                {
                    "field": location or None,
                    "message": error.get("msg", "Geçersiz değer."),
                }
            )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Gönderilen bilgiler geçersiz.",
                "errors": errors,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception(
            "Unhandled API error on %s %s",
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": (
                    "Sunucuda beklenmeyen bir hata oluştu. "
                    "Lütfen daha sonra tekrar deneyin."
                )
            },
        )
