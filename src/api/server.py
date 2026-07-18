"""
FastAPI application server.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.auth import APIKeyMiddleware
from src.api.rate_limiter import RateLimitMiddleware
from src.api.security_headers import add_security_headers
from src.api.error_handlers import add_error_handlers
from src.config import get_settings
from src.utils.logger import get_logger
from src.utils.metrics import add_metrics_endpoint, add_metrics_middleware

logger = get_logger(__name__)

SHUTDOWN_TIMEOUT = 15


def _run_startup_checks(app: FastAPI) -> None:
    """Run configuration validation and backend connectivity checks on startup."""
    settings = get_settings()
    warnings: list[str] = []

    missing = settings.validate_required_keys()
    for key in missing:
        warnings.append(f"Missing required API key: {key}")

    if not warnings:
        logger.info("Startup checks passed — all required configuration present")
    else:
        for w in warnings:
            logger.warning(w)


async def _cancel_pending_tasks(app: FastAPI) -> None:
    """Cancel all pending research jobs with graceful timeout."""
    pending = app.state.active_tasks
    if not pending:
        logger.info("No active jobs to cancel")
        return

    count = len(pending)
    logger.info(f"Cancelling {count} active research jobs...")
    for job_id, task in list(pending.items()):
        if not task.done():
            task.cancel()

    done, pending_wait = await asyncio.wait(
        list(pending.values()),
        timeout=SHUTDOWN_TIMEOUT,
        return_when=asyncio.ALL_COMPLETED,
    )
    completed = len(done)
    still_running = len(pending_wait)
    if still_running:
        logger.warning(f"{still_running} job(s) did not finish within {SHUTDOWN_TIMEOUT}s — force-closing")
        for task in pending_wait:
            task.cancel()
    logger.info(f"Shutdown complete: {completed} cancelled, {still_running} force-closed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup/shutdown."""
    logger.info("Starting Research Lab API server...")
    app.state.start_time = datetime.now(UTC)
    app.state.jobs: dict[str, Any] = {}
    app.state.active_tasks: dict[str, asyncio.Task] = {}

    _run_startup_checks(app)

    try:
        from src.memory.history import get_run_history
        get_run_history()
        logger.info("SQLite run history initialized")
        from src.config import get_settings
        logger.info(f"CELERY_BROKER_URL: {get_settings().celery_broker_url}")
    except Exception as e:
        logger.warning(f"SQLite init failed (will use in-memory only): {e}")

    yield

    logger.info("Shutting down Research Lab API server...")
    await _cancel_pending_tasks(app)

    from src.api.websocket_manager import get_connection_manager
    mgr = get_connection_manager()
    ws_count = mgr.connected_count()
    if ws_count:
        logger.info(f"Closing {ws_count} WebSocket connection(s)")

    logger.info("Goodbye.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Multi-Agent Research Lab API",
        description="AI-powered multi-agent research system with quality loops, WebSocket streaming, and SQLite persistence",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(APIKeyMiddleware)

    add_security_headers(app)
    add_error_handlers(app)

    from src.api.routes import router
    app.include_router(router, prefix="/api/v1")

    @app.get("/")
    async def root():
        return {
            "status": "alive",
            "service": "Multi-Agent Research Lab API",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/api/v1/health"
        }

    @app.get("/api/v1")
    async def api_v1_root():
        return {
            "status": "alive",
            "version": "v1",
            "endpoints": {
                "health": "/api/v1/health",
                "research": "/api/v1/research"
            }
        }
    add_metrics_middleware(app)
    add_metrics_endpoint(app)

    return app


def get_app() -> FastAPI:
    """Get or create the FastAPI application singleton."""
    if not hasattr(get_app, "_app"):
        get_app._app = create_app()
    return get_app._app


app = get_app()
