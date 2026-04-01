"""WebSocket connection manager for real-time crawl progress streaming."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts messages."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections = [*self.active_connections, websocket]

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the active list."""
        self.active_connections = [
            conn for conn in self.active_connections if conn is not websocket
        ]

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to all active connections, removing dead ones."""
        dead: list[WebSocket] = []
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                logger.warning("Removing dead WebSocket connection")
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn)
