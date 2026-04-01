from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from ceres.api.websocket import ConnectionManager


class TestConnectionManager:
    @pytest.mark.asyncio
    async def test_connect_adds_to_active(self):
        manager = ConnectionManager()
        ws = AsyncMock()
        await manager.connect(ws)
        assert len(manager.active_connections) == 1

    @pytest.mark.asyncio
    async def test_disconnect_removes(self):
        manager = ConnectionManager()
        ws = AsyncMock()
        await manager.connect(ws)
        manager.disconnect(ws)
        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self):
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await manager.connect(ws1)
        await manager.connect(ws2)
        await manager.broadcast({"event": "test"})
        ws1.send_json.assert_called_once_with({"event": "test"})
        ws2.send_json.assert_called_once_with({"event": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self):
        manager = ConnectionManager()
        ws_good = AsyncMock()
        ws_bad = AsyncMock()
        ws_bad.send_json.side_effect = Exception("closed")
        await manager.connect(ws_good)
        await manager.connect(ws_bad)
        await manager.broadcast({"event": "test"})
        assert len(manager.active_connections) == 1
