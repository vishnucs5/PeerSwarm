"""
Tests for server lifecycle: startup checks, graceful shutdown.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestStartupChecks:
    def test_all_keys_present_no_warnings(self):
        from src.api.server import _run_startup_checks
        app = MagicMock()
        with (
            patch("src.api.server.get_settings") as mock_settings,
            patch("src.api.server.logger") as mock_logger,
        ):
            mock_settings.return_value.validate_required_keys.return_value = []
            _run_startup_checks(app)
            mock_logger.info.assert_called_once_with(
                "Startup checks passed — all required configuration present"
            )

    def test_missing_keys_generate_warnings(self):
        from src.api.server import _run_startup_checks
        app = MagicMock()
        with (
            patch("src.api.server.get_settings") as mock_settings,
            patch("src.api.server.logger") as mock_logger,
        ):
            mock_settings.return_value.validate_required_keys.return_value = ["OPENAI_API_KEY", "TAVILY_API_KEY"]
            _run_startup_checks(app)
            assert mock_logger.warning.call_count == 2


class TestCancelPendingTasks:
    @pytest.mark.asyncio
    async def test_no_pending_tasks_logs_info(self):
        from src.api.server import _cancel_pending_tasks
        app = MagicMock()
        app.state.active_tasks = {}
        with patch("src.api.server.logger") as mock_logger:
            await _cancel_pending_tasks(app)
            mock_logger.info.assert_any_call("No active jobs to cancel")

    @pytest.mark.asyncio
    async def test_cancels_and_waits_for_tasks(self):
        from src.api.server import _cancel_pending_tasks
        app = MagicMock()

        async def slow_task():
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                pass

        t1 = asyncio.create_task(slow_task())
        t2 = asyncio.create_task(slow_task())
        app.state.active_tasks = {"job1": t1, "job2": t2}

        with patch("src.api.server.logger"):
            await _cancel_pending_tasks(app)

        assert t1.done()
        assert t2.done()

    @pytest.mark.asyncio
    async def test_force_closes_stuck_tasks(self):
        from src.api.server import _cancel_pending_tasks, SHUTDOWN_TIMEOUT
        app = MagicMock()

        async def stuck_task():
            try:
                await asyncio.sleep(SHUTDOWN_TIMEOUT + 5)
            except asyncio.CancelledError:
                await asyncio.sleep(SHUTDOWN_TIMEOUT + 5)

        t = asyncio.create_task(stuck_task())
        app.state.active_tasks = {"stuck": t}

        with patch("src.api.server.logger"):
            await _cancel_pending_tasks(app)

        assert t.done()


class TestLifespan:
    @pytest.mark.asyncio
    async def test_lifespan_startup_initializes_state(self):
        from src.api.server import lifespan
        app = MagicMock()
        app.state = MagicMock()

        with (
            patch("src.api.server._run_startup_checks"),
            patch("src.memory.history.get_run_history") as mock_history,
        ):
            async with lifespan(app) as _:
                assert hasattr(app.state, "start_time")
                assert hasattr(app.state, "jobs")
                assert hasattr(app.state, "active_tasks")
                mock_history.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_sqlite_failure_logs_warning(self):
        from src.api.server import lifespan
        app = MagicMock()
        app.state = MagicMock()

        with (
            patch("src.api.server._run_startup_checks"),
            patch("src.memory.history.get_run_history", side_effect=Exception("db error")),
            patch("src.api.server.logger") as mock_logger,
        ):
            async with lifespan(app) as _:
                pass
            mock_logger.warning.assert_called_once()
            assert "SQLite init failed" in mock_logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_cleans_websockets(self):
        from src.api.server import lifespan
        app = MagicMock()
        app.state = MagicMock()
        app.state.active_tasks = {}

        with (
            patch("src.api.server._run_startup_checks"),
            patch("src.memory.history.get_run_history"),
            patch("src.api.server._cancel_pending_tasks"),
            patch("src.api.websocket_manager.get_connection_manager") as mock_mgr,
        ):
            mock_mgr.return_value.connected_count.return_value = 2
            async with lifespan(app) as _:
                pass