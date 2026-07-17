"""
Prometheus metrics for observability.
"""
from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from prometheus_client.registry import REGISTRY

# ── Metrics ──────────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "research_http_requests_total",
    "Total HTTP requests",
    labelnames=["method", "path", "status"],
)

REQUEST_DURATION = Histogram(
    "research_http_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

ACTIVE_JOBS = Gauge(
    "research_active_jobs",
    "Number of currently active research jobs",
)

WEBSOCKET_CONNECTIONS = Gauge(
    "research_websocket_connections",
    "Number of active WebSocket connections",
)

DB_OPERATIONS = Counter(
    "research_db_operations_total",
    "Total database operations",
    labelnames=["backend", "operation", "status"],
)

RATE_LIMIT_HITS = Counter(
    "research_rate_limit_hits_total",
    "Total rate limit hits",
)


def add_metrics_middleware(app: FastAPI) -> None:
    """Middleware that records request count and duration."""
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next: Callable) -> Response:
        method = request.method
        path = request.url.path

        start_time = time.monotonic()
        try:
            response = await call_next(request)
            status = str(response.status_code)
            REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
            return response
        except Exception:
            REQUEST_COUNT.labels(method=method, path=path, status="5xx").inc()
            raise
        finally:
            duration = time.monotonic() - start_time
            REQUEST_DURATION.labels(method=method, path=path).observe(duration)


def add_metrics_endpoint(app: FastAPI) -> None:
    """Add /metrics endpoint exposing Prometheus metrics."""
    from fastapi.responses import PlainTextResponse

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return PlainTextResponse(generate_latest(REGISTRY).decode("utf-8"), media_type="text/plain")


def update_active_jobs(count: int) -> None:
    ACTIVE_JOBS.set(count)


def update_websocket_connections(count: int) -> None:
    WEBSOCKET_CONNECTIONS.set(count)


def inc_db_operation(backend: str, operation: str, status: str = "ok") -> None:
    DB_OPERATIONS.labels(backend=backend, operation=operation, status=status).inc()


def inc_rate_limit_hit() -> None:
    RATE_LIMIT_HITS.inc()
