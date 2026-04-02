"""Tests for Redis pub/sub to WebSocket bridge."""

from __future__ import annotations

import json

import pytest
from unittest.mock import AsyncMock

from ceres.pubsub import PubSubBridge


class TestPubSubBridge:
    @pytest.mark.asyncio
    async def test_handle_message_relays_to_broadcast(self):
        broadcast = AsyncMock()
        bridge = PubSubBridge(redis_url="redis://localhost:6379", broadcast=broadcast)

        event = {"job_id": "j1", "agent": "strategist", "status": "running", "timestamp": "2026-04-02T00:00:00Z"}
        await bridge._handle_message(json.dumps(event).encode())

        broadcast.assert_called_once()
        call_arg = broadcast.call_args[0][0]
        assert call_arg["type"] == "job_status"
        assert call_arg["job_id"] == "j1"
        assert call_arg["agent"] == "strategist"
        assert call_arg["status"] == "running"

    @pytest.mark.asyncio
    async def test_handle_message_ignores_malformed_json(self):
        broadcast = AsyncMock()
        bridge = PubSubBridge(redis_url="redis://localhost:6379", broadcast=broadcast)

        await bridge._handle_message(b"not json")
        broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_catches_broadcast_errors(self):
        broadcast = AsyncMock(side_effect=Exception("WebSocket dead"))
        bridge = PubSubBridge(redis_url="redis://localhost:6379", broadcast=broadcast)

        event = {"job_id": "j2", "status": "success"}
        # Should not raise
        await bridge._handle_message(json.dumps(event).encode())
        broadcast.assert_called_once()
