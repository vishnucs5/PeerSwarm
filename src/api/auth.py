"""
API key authentication middleware.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

PUBLIC_PATHS = {
    "/",
    "/api/v1",
    "/api/v1/health",
    "/api/v1/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        settings = get_settings()
        if not settings.security.api_key_enabled:
            return await call_next(request)

        path = request.url.path
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PATHS if p not in ("/", "/api/v1")):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not api_key:
            logger.warning("missing_api_key", path=path)
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Unauthorized",
                    "detail": "Missing X-API-Key header",
                    "code": "MISSING_API_KEY",
                },
            )

        if api_key not in settings.security.api_keys:
            logger.warning("invalid_api_key", path=path)
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Forbidden",
                    "detail": "Invalid API key",
                    "code": "INVALID_API_KEY",
                },
            )

        return await call_next(request)
