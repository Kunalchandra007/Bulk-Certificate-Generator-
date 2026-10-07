"""Custom exceptions and FastAPI exception handlers.

All API errors use a consistent shape: {"detail": "...", "code": "SOME_CODE"}.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application error with an HTTP status code and machine-readable code."""

    def __init__(self, status_code: int, detail: str, code: str) -> None:
        self.status_code = status_code
        self.detail = detail
        self.code = code


class NotFoundError(AppError):
    def __init__(self, detail: str = "Resource not found") -> None:
        super().__init__(404, detail, "NOT_FOUND")


class ConflictError(AppError):
    def __init__(self, detail: str = "Conflict") -> None:
        super().__init__(409, detail, "CONFLICT")


class ValidationError(AppError):
    def __init__(self, detail: str = "Validation error") -> None:
        super().__init__(422, detail, "VALIDATION_ERROR")


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers so every error returns the standard JSON shape."""

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "code": exc.code},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
        # Never leak stack traces in API responses
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "code": "INTERNAL_ERROR"},
        )
