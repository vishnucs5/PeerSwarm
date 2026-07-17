"""
WebSocket manager for real-time job updates.
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

from src.utils.logger import get_logger
from src.utils.metrics import update_websocket_connections

logger = get_logger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections per job_id.
    Supports broadcasting status updates to all subscribers of a job.
    """

    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, job_id: str):
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(job_id, set()).add(websocket)
        update_websocket_connections(self.connected_count())
        logger.debug(f"WebSocket connected for job {job_id}")

    async def disconnect(self, websocket: WebSocket, job_id: str):
        async with self._lock:
            if job_id in self._connections:
                self._connections[job_id].discard(websocket)
                if not self._connections[job_id]:
                    del self._connections[job_id]
        update_websocket_connections(self.connected_count())
        logger.debug(f"WebSocket disconnected for job {job_id}")

    async def broadcast(self, job_id: str, event: str, data: dict[str, Any]):
        """Send a JSON message to all subscribers of a job."""
        async with self._lock:
            connections = set(self._connections.get(job_id, set()))

        if not connections:
            return

        message = json.dumps({
            "event": event,
            "job_id": job_id,
            "data": data,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        })

        stale = set()
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                stale.add(ws)

        if stale:
            async with self._lock:
                for ws in stale:
                    self._connections[job_id].discard(ws)
                if job_id in self._connections and not self._connections[job_id]:
                    del self._connections[job_id]

    async def broadcast_status(self, job_id: str, status: str, **extra):
        """Convenience: broadcast a status update."""
        await self.broadcast(job_id, "status_update", {
            "status": status,
            **extra,
        })

    async def broadcast_quality(self, job_id: str, score: dict[str, Any], iteration: int):
        """Broadcast quality score update."""
        await self.broadcast(job_id, "quality_update", {
            "score": score,
            "iteration": iteration,
        })

    async def broadcast_complete(self, job_id: str, report_path: str | None = None):
        """Broadcast job completion."""
        await self.broadcast(job_id, "job_complete", {
            "report_path": report_path,
        })

    async def broadcast_error(self, job_id: str, error: str):
        """Broadcast job error."""
        await self.broadcast(job_id, "job_error", {
            "error": error,
        })

    def connected_count(self) -> int:
        """Total connected clients."""
        return sum(len(conns) for conns in self._connections.values())


# Global singleton
_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
