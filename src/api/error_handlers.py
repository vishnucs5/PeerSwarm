"""
Standardized error handling with RFC 7807 Problem Details support.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.utils.logger import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base application error."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    """Resource not found error."""

    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            message=f"{resource} not found: {resource_id}",
            code="NOT_FOUND",
            status_code=404,
            details={"resource": resource, "id": resource_id},
        )


class ValidationError(AppError):
    """Request validation error."""

    def __init__(self, message: str, details: list[dict[str, Any]] | None = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details={"errors": details} if details else None,
        )


class UnauthorizedError(AppError):
    """Authentication required error."""

    def __init__(self, reason: str = "Authentication required"):
        super().__init__(
            message=reason,
            code="UNAUTHORIZED",
            status_code=401,
        )


class ForbiddenError(AppError):
    """Authorization denied error."""

    def __init__(self, reason: str = "Access denied"):
        super().__init__(
            message=reason,
            code="FORBIDDEN",
            status_code=403,
        )


class RateLimitError(AppError):
    """Rate limit exceeded error."""

    def __init__(self, retry_after_seconds: int = 60):
        super().__init__(
            message="Rate limit exceeded",
            code="RATE_LIMITED",
            status_code=429,
            details={"retry_after_seconds": retry_after_seconds},
        )


class ExternalServiceError(AppError):
    """External service error (API failures)."""

    def __init__(self, service: str, message: str, status_code: int = 502):
        super().__init__(
            message=f"{service} error: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            status_code=status_code,
            details={"service": service},
        )


class CircuitBreakerOpenError(AppError):
    """Circuit breaker is open, service unavailable."""

    def __init__(self, service: str, retry_after_seconds: int = 60):
        super().__init__(
            message=f"Circuit breaker open for {service}. Service temporarily unavailable.",
            code="CIRCUIT_BREAKER_OPEN",
            status_code=503,
            details={"service": service, "retry_after_seconds": retry_after_seconds},
        )


class ErrorResponse:
    """RFC 7807 Problem Details response format."""

    @staticmethod
    def from_exception(exc: Exception) -> JSONResponse:
        if isinstance(exc, AppError):
            content = {
                "type": f"/errors/{exc.code.lower()}",
                "title": exc.code,
                "status": exc.status_code,
                "detail": exc.message,
            }
            if exc.details:
                content["errors"] = exc.details
            return JSONResponse(status_code=exc.status_code, content=content)

        if isinstance(exc, ValidationError):
            return JSONResponse(
                status_code=422,
                content={
                    "type": "/errors/validation-error",
                    "title": "VALIDATION_ERROR",
                    "status": 422,
                    "detail": "Request validation failed",
                    "errors": exc.errors(),
                },
            )

        logger.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "type": "/errors/internal",
                "title": "INTERNAL_ERROR",
                "status": 500,
                "detail": "An unexpected error occurred. Please try again later.",
            },
        )


def add_error_handlers(app: FastAPI) -> None:
    """Register global error handlers on the FastAPI app."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return ErrorResponse.from_exception(exc)

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return ErrorResponse.from_exception(exc)

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return ErrorResponse.from_exception(exc)

    logger.info("Global error handlers registered")
