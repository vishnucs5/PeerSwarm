"""
In-memory sliding-window rate limiter for FastAPI with periodic cleanup.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.config import get_settings
from src.utils.logger import get_logger
from src.utils.metrics import inc_rate_limit_hit

logger = get_logger(__name__)


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int = 60, window_seconds: int = 60, cleanup_interval: int = 300):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.cleanup_interval = cleanup_interval
        self._clients: dict[str, list[float]] = defaultdict(list)
        self._cleanup_task: asyncio.Task | None = None

    def _get_client_key(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def is_allowed(self, request: Request) -> tuple[bool, int, int]:
        if self.max_requests <= 0:
            return False, 0, self.window_seconds
        key = self._get_client_key(request)
        now = time.time()
        cutoff = now - self.window_seconds
        timestamps = self._clients[key]
        timestamps[:] = [t for t in timestamps if t > cutoff]
        count = len(timestamps)
        remaining = max(0, self.max_requests - count)
        if count >= self.max_requests:
            retry_after = int(timestamps[0] + self.window_seconds - now) if timestamps else self.window_seconds
            return False, remaining, retry_after
        timestamps.append(now)
        remaining = max(0, self.max_requests - len(timestamps))
        return True, remaining, 0

    def _cleanup_old_entries(self) -> int:
        """Remove expired timestamps from all clients. Returns number of entries removed."""
        now = time.time()
        cutoff = now - self.window_seconds
        total_removed = 0
        for key, timestamps in list(self._clients.items()):
            original_len = len(timestamps)
            timestamps[:] = [t for t in timestamps if t > cutoff]
            removed = original_len - len(timestamps)
            total_removed += removed
            if not timestamps:
                del self._clients[key]
        return total_removed

    async def start_cleanup_task(self):
        """Start periodic cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_task(self):
        """Stop periodic cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_loop(self):
        """Periodic cleanup loop."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                removed = self._cleanup_old_entries()
                if removed > 0:
                    logger.debug(f"Rate limiter cleanup: removed {removed} expired entries")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Rate limiter cleanup error: {e}")


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI):
        super().__init__(app)
        settings = get_settings()
        self.limiter = SlidingWindowRateLimiter(
            max_requests=settings.server.rate_limit_requests,
            window_seconds=settings.server.rate_limit_window_seconds,
            cleanup_interval=300,  # 5 minutes
        )

    async def dispatch(self, request: Request, call_next):
        # Start cleanup task on first request
        await self.limiter.start_cleanup_task()
        
        allowed, remaining, retry_after = self.limiter.is_allowed(request)
        if not allowed:
            inc_rate_limit_hit()
            logger.warning("rate_limit_exceeded", client=self.limiter._get_client_key(request))
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": f"Rate limit exceeded. Retry after {retry_after} seconds.",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "X-RateLimit-Limit": str(self.limiter.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time() + retry_after)),
                    "Retry-After": str(retry_after),
                },
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limiter.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(
            int(time.time() + self.limiter.window_seconds)
        )
        return response
