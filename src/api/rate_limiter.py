"""
Redis-backed sliding-window rate limiter for multi-worker FastAPI deployments.
Falls back to in-memory when Redis is unavailable.
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


class InMemoryRateLimiter:
    """In-memory sliding-window rate limiter (fallback when Redis unavailable)."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clients: dict[str, list[float]] = defaultdict(list)

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

    def cleanup_old_entries(self) -> int:
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

    def _cleanup_old_entries(self) -> int:
        return self.cleanup_old_entries()



class RedisRateLimiter:
    """Redis-backed sliding-window rate limiter for multi-worker deployments."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60, redis_url: str = "redis://localhost:6379/0"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.redis_url = redis_url
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = await aioredis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                await self._redis.ping()
            except Exception as e:
                logger.warning(f"Redis connection failed, falling back to in-memory: {e}")
                return None
        return self._redis

    def _get_client_key(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def is_allowed(self, request: Request) -> tuple[bool, int, int]:
        if self.max_requests <= 0:
            return False, 0, self.window_seconds

        r = await self._get_redis()
        if r is None:
            return False, 0, self.window_seconds

        key = f"rate_limit:{self._get_client_key(request)}"
        now = time.time()
        cutoff = now - self.window_seconds

        try:
            pipe = r.pipeline()
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, self.window_seconds)
            results = await pipe.execute()

            count = results[1]
            if count >= self.max_requests:
                retry_after = int(self.window_seconds)
                return False, 0, retry_after

            remaining = max(0, self.max_requests - count - 1)
            return True, remaining, 0
        except Exception as e:
            logger.warning(f"Redis rate limit error: {e}")
            return True, self.max_requests, 0

    async def cleanup_old_entries(self) -> int:
        r = await self._get_redis()
        if r is None:
            return 0

        try:
            keys = []
            async for key in r.scan_iter("rate_limit:*"):
                keys.append(key)

            cutoff = time.time() - self.window_seconds
            total_removed = 0
            for key in keys:
                removed = await r.zremrangebyscore(key, 0, cutoff)
                total_removed += removed
            return total_removed
        except Exception as e:
            logger.warning(f"Redis cleanup error: {e}")
            return 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit middleware with Redis backend and in-memory fallback."""

    def __init__(self, app: FastAPI):
        super().__init__(app)
        settings = get_settings()
        self.max_requests = settings.server.rate_limit_requests
        self.window_seconds = settings.server.rate_limit_window_seconds

        # Try Redis first, fallback to in-memory
        redis_url = getattr(settings, "celery_broker_url", None)
        if redis_url:
            self.limiter = RedisRateLimiter(
                max_requests=self.max_requests,
                window_seconds=self.window_seconds,
                redis_url=redis_url,
            )
            self._limiter_type = "redis"
        else:
            self.limiter = InMemoryRateLimiter(
                max_requests=self.max_requests,
                window_seconds=self.window_seconds,
            )
            self._limiter_type = "in-memory"

        self._cleanup_task: asyncio.Task | None = None

    async def _start_cleanup(self):
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        while True:
            try:
                await asyncio.sleep(300)
                if hasattr(self.limiter, 'cleanup_old_entries'):
                    removed = await self.limiter.cleanup_old_entries()
                    if removed > 0:
                        logger.debug(f"Rate limiter cleanup: removed {removed} expired entries")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Rate limiter cleanup error: {e}")

    def _get_client_key(self, request: Request) -> str:
        if hasattr(self.limiter, '_get_client_key'):
            return self.limiter._get_client_key(request)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        await self._start_cleanup()

        if self._limiter_type == "redis":
            allowed, remaining, retry_after = await self.limiter.is_allowed(request)
        else:
            allowed, remaining, retry_after = self.limiter.is_allowed(request)

        if not allowed:
            inc_rate_limit_hit()
            logger.warning("rate_limit_exceeded", client=self._get_client_key(request))
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": f"Rate limit exceeded. Retry after {retry_after} seconds.",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time() + retry_after)),
                    "Retry-After": str(retry_after),
                },
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(
            int(time.time() + self.window_seconds)
        )
        return response


# Alias for backward compatibility (e.g. tests)
SlidingWindowRateLimiter = InMemoryRateLimiter

