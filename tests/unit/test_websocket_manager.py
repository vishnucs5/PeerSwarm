"""
Tests for the WebSocket connection manager.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def manager():
    from src.api.websocket_manager import ConnectionManager
    return ConnectionManager()


@pytest.fixture
def mock_ws():
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


@pytest.mark.asyncio
class TestConnectionManager:
    async def test_initial_state(self, manager):
        assert manager.connected_count() == 0

    async def test_connect_disconnect(self, manager, mock_ws):
        await manager.connect(mock_ws, "job-1")
        assert manager.connected_count() == 1

        await manager.disconnect(mock_ws, "job-1")
        assert manager.connected_count() == 0

    async def test_broadcast_sends_to_subscribers(self, manager, mock_ws):
        await manager.connect(mock_ws, "job-1")
        await manager.broadcast("job-1", "test_event", {"msg": "hello"})
        mock_ws.send_text.assert_awaited_once()

    async def test_broadcast_unknown_job_no_error(self, manager):
        await manager.broadcast("nonexistent", "test", {})

    async def test_multiple_connections_same_job(self, manager):
        ws1 = MagicMock(accept=AsyncMock(), send_text=AsyncMock())
        ws2 = MagicMock(accept=AsyncMock(), send_text=AsyncMock())
        await manager.connect(ws1, "job-1")
        await manager.connect(ws2, "job-1")
        assert manager.connected_count() == 2

        await manager.disconnect(ws1, "job-1")
        assert manager.connected_count() == 1

    async def test_broadcast_all_subscribers(self, manager):
        ws1 = MagicMock(accept=AsyncMock(), send_text=AsyncMock())
        ws2 = MagicMock(accept=AsyncMock(), send_text=AsyncMock())
        await manager.connect(ws1, "job-1")
        await manager.connect(ws2, "job-1")
        await manager.broadcast("job-1", "test", {})
        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_awaited_once()

    async def test_broadcast_status(self, manager, mock_ws):
        await manager.connect(mock_ws, "job-1")
        await manager.broadcast_status("job-1", "completed")
        mock_ws.send_text.assert_awaited_once()
        args, _ = mock_ws.send_text.await_args
        assert "status_update" in args[0]

    async def test_broadcast_quality(self, manager, mock_ws):
        await manager.connect(mock_ws, "job-1")
        await manager.broadcast_quality("job-1", {"overall": 8.5}, 2)
        mock_ws.send_text.assert_awaited_once()

    async def test_broadcast_complete(self, manager, mock_ws):
        await manager.connect(mock_ws, "job-1")
        await manager.broadcast_complete("job-1", report_path="output.md")
        mock_ws.send_text.assert_awaited_once()

    async def test_broadcast_error(self, manager, mock_ws):
        await manager.connect(mock_ws, "job-1")
        await manager.broadcast_error("job-1", "something went wrong")
        mock_ws.send_text.assert_awaited_once()

    async def test_stale_connection_removed_on_broadcast(self, manager, mock_ws):
        await manager.connect(mock_ws, "job-1")
        mock_ws.send_text.side_effect = Exception("disconnected")
        await manager.broadcast("job-1", "test", {})
        assert manager.connected_count() == 0