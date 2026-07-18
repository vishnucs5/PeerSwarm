"""
Tests for API key authentication middleware.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from starlette.datastructures import Headers


async def _call_middleware(middleware, path: str, api_key: str | None = None):
    """Helper: create a mock request and call dispatch."""
    raw_headers = []
    if api_key is not None:
        raw_headers.append((b"x-api-key", api_key.encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": raw_headers,
    }
    request = MagicMock()
    request.url.path = path
    request.headers = Headers(scope=scope)
    response = MagicMock()
    response.status_code = 200

    async def call_next(req):
        return response

    return await middleware.dispatch(request, call_next)


class TestAPIKeyMiddleware:
    @pytest.mark.asyncio
    async def test_passthrough_when_disabled(self):
        from src.api.auth import APIKeyMiddleware

        app = MagicMock()
        middleware = APIKeyMiddleware(app)
        with patch("src.api.auth.get_settings") as mock_settings:
            mock_settings.return_value.security.api_key_enabled = False
            result = await _call_middleware(middleware, "/api/v1/research")
            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_public_paths_bypass_auth(self):
        from src.api.auth import APIKeyMiddleware

        app = MagicMock()
        middleware = APIKeyMiddleware(app)
        with patch("src.api.auth.get_settings") as mock_settings:
            mock_settings.return_value.security.api_key_enabled = True
            mock_settings.return_value.security.api_keys = ["secret-123"]
            for path in ["/api/v1/health", "/docs", "/redoc", "/openapi.json"]:
                result = await _call_middleware(middleware, path)
                assert result.status_code == 200, f"Failed for {path}"

    @pytest.mark.asyncio
    async def test_missing_key_returns_401(self):
        from src.api.auth import APIKeyMiddleware

        app = MagicMock()
        middleware = APIKeyMiddleware(app)
        with patch("src.api.auth.get_settings") as mock_settings:
            mock_settings.return_value.security.api_key_enabled = True
            mock_settings.return_value.security.api_keys = ["secret-123"]
            result = await _call_middleware(middleware, "/api/v1/research")
            assert result.status_code == 401
            body = result.body.decode()
            assert "MISSING_API_KEY" in body

    @pytest.mark.asyncio
    async def test_invalid_key_returns_403(self):
        from src.api.auth import APIKeyMiddleware

        app = MagicMock()
        middleware = APIKeyMiddleware(app)
        with patch("src.api.auth.get_settings") as mock_settings:
            mock_settings.return_value.security.api_key_enabled = True
            mock_settings.return_value.security.api_keys = ["secret-123"]
            result = await _call_middleware(middleware, "/api/v1/research", api_key="wrong-key")
            assert result.status_code == 403
            body = result.body.decode()
            assert "INVALID_API_KEY" in body

    @pytest.mark.asyncio
    async def test_valid_key_passes(self):
        from src.api.auth import APIKeyMiddleware

        app = MagicMock()
        middleware = APIKeyMiddleware(app)
        with patch("src.api.auth.get_settings") as mock_settings:
            mock_settings.return_value.security.api_key_enabled = True
            mock_settings.return_value.security.api_keys = ["valid-key-1", "valid-key-2"]
            result = await _call_middleware(middleware, "/api/v1/research", api_key="valid-key-1")
            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_options_preflight_bypasses_auth(self):
        from src.api.auth import APIKeyMiddleware

        app = MagicMock()
        middleware = APIKeyMiddleware(app)
        with patch("src.api.auth.get_settings") as mock_settings:
            mock_settings.return_value.security.api_key_enabled = True
            mock_settings.return_value.security.api_keys = ["secret-123"]
            scope = {
                "type": "http",
                "method": "OPTIONS",
                "path": "/api/v1/research",
                "headers": [],
            }
            request = MagicMock()
            request.url.path = "/api/v1/research"
            request.method = "OPTIONS"
            request.headers = Headers(scope=scope)
            response = MagicMock()
            response.status_code = 200

            async def call_next(req):
                return response

            result = await middleware.dispatch(request, call_next)
            assert result.status_code == 200
