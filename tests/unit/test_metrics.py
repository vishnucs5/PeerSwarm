"""
Tests for Prometheus metrics.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from prometheus_client import REGISTRY

from src.utils.metrics import (
    ACTIVE_JOBS,
    DB_OPERATIONS,
    RATE_LIMIT_HITS,
    REQUEST_COUNT,
    REQUEST_DURATION,
    WEBSOCKET_CONNECTIONS,
    inc_db_operation,
    inc_rate_limit_hit,
    update_active_jobs,
    update_websocket_connections,
)


class TestMetrics:
    def _sample(self, metric, name: str) -> float:
        sample = next(s for s in metric.collect()[0].samples if s.name == name)
        return sample.value

    def test_request_count(self):
        REQUEST_COUNT.labels(method="GET", path="/test", status="200").inc()
        value = self._sample(REQUEST_COUNT, "research_http_requests_total")
        assert value >= 1

    def test_active_jobs_gauge(self):
        update_active_jobs(5)
        assert ACTIVE_JOBS._value.get() == 5.0
        update_active_jobs(3)
        assert ACTIVE_JOBS._value.get() == 3.0

    def test_websocket_connections_gauge(self):
        update_websocket_connections(10)
        assert WEBSOCKET_CONNECTIONS._value.get() == 10.0
        update_websocket_connections(0)
        assert WEBSOCKET_CONNECTIONS._value.get() == 0.0

    def test_db_operations_counter(self):
        inc_db_operation("chromadb", "add", "ok")
        inc_db_operation("neo4j", "search", "ok")
        inc_db_operation("chromadb", "add", "error")
        samples = [s for s in DB_OPERATIONS.collect()[0].samples if s.name == "research_db_operations_total"]
        assert len(samples) >= 3

    def test_rate_limit_hits_counter(self):
        before = self._sample(RATE_LIMIT_HITS, "research_rate_limit_hits_total")
        inc_rate_limit_hit()
        after = self._sample(RATE_LIMIT_HITS, "research_rate_limit_hits_total")
        assert after == before + 1

    def test_metrics_endpoint_returns_plaintext(self):
        from prometheus_client import generate_latest
        output = generate_latest(REGISTRY).decode("utf-8")
        assert "# HELP" in output
        assert "# TYPE" in output
        assert "research_http_requests_total" in output
        assert "research_active_jobs" in output
        assert "research_websocket_connections" in output
        assert "research_db_operations_total" in output
        assert "research_rate_limit_hits_total" in output
        assert "research_http_request_duration_seconds" in output

    @pytest.mark.asyncio
    async def test_health_endpoint_enhanced(self):
        """Verify enhanced /health returns backend checks."""
        from src.api.routes import router
        from fastapi import FastAPI
        from httpx import AsyncClient, ASGITransport
        app = FastAPI()
        import datetime
        app.state.start_time = datetime.datetime.now(datetime.timezone.utc)
        app.state.jobs = {}
        app.state.active_tasks = {}
        app.include_router(router, prefix="/api/v1")
        from src.api.websocket_manager import get_connection_manager
        # Mock backends to avoid real connections
        mgr = get_connection_manager()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/health")
            assert resp.status_code == 200
            data = resp.json()
            assert "status" in data
            assert "services" in data
            assert "sqlite" in data["services"]
            assert "chromadb" in data["services"]
            assert "neo4j" in data["services"]
            assert "redis" in data["services"]
            assert "websocket" in data["services"]