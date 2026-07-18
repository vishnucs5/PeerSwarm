"""
Security headers middleware for FastAPI.
Implements CSP, HSTS, X-Frame-Options, and other security headers.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.utils.logger import get_logger

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    def __init__(self, app: FastAPI):
        super().__init__(app)
        self._headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
            "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self' http://localhost:* ws://localhost:* wss://localhost:*; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            ),
        }

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        for header, value in self._headers.items():
            response.headers[header] = value

        # Remove server header
        if "server" in response.headers:
            del response.headers["server"]

        return response


def add_security_headers(app: FastAPI) -> None:
    """Add security headers middleware to the FastAPI app."""
    app.add_middleware(SecurityHeadersMiddleware)
    logger.info("Security headers middleware added")
