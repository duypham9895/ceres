"""Redis pub/sub subscriber that bridges job events to WebSocket broadcast."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Optional

import redis.asyncio as aioredis

from ceres.queue import CHANNEL

logger = logging.getLogger(__name__)


class PubSubBridge:
    """Subscribes to Redis pub/sub and relays events to a broadcast callback."""

    def __init__(
        self,
        redis_url: str,
        broadcast: Callable[[dict], Coroutine[Any, Any, None]],
    ) -> None:
        self._redis_url = redis_url
        self._broadcast = broadcast
        self._task: Optional[asyncio.Task] = None
        self._redis: Optional[aioredis.Redis] = None

    async def start(self) -> None:
        """Connect to Redis and start listening in a background task."""
        self._redis = aioredis.from_url(self._redis_url)
        self._task = asyncio.create_task(self._listen())
        logger.info("PubSubBridge started on channel %s", CHANNEL)

    async def stop(self) -> None:
        """Cancel the listener and close Redis connection."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._redis is not None:
            await self._redis.aclose()

    async def _listen(self) -> None:
        """Subscribe and relay messages with reconnection on failure."""
        backoff = 1.0
        max_backoff = 30.0
        pubsub = None
        while True:
            try:
                pubsub = self._redis.pubsub()
                await pubsub.subscribe(CHANNEL)
                backoff = 1.0
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        await self._handle_message(message["data"])
            except asyncio.CancelledError:
                if pubsub is not None:
                    try:
                        await pubsub.unsubscribe(CHANNEL)
                        await pubsub.close()
                    except Exception:
                        pass
                raise
            except Exception:
                if pubsub is not None:
                    try:
                        await pubsub.close()
                    except Exception:
                        pass
                logger.warning(
                    "PubSub connection lost, reconnecting in %.0fs", backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    async def _handle_message(self, data: bytes) -> None:
        """Parse a pub/sub message and broadcast it.

        Maps arq worker status values to the event types the dashboard expects:
          running -> job_start, success -> job_finish, error -> job_error.
        """
        try:
            event = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Ignoring malformed pub/sub message")
            return

        _STATUS_TO_TYPE = {
            "running": "job_start",
            "success": "job_finish",
            "error": "job_error",
        }
        event_status = event.get("status", "")
        event_type = _STATUS_TO_TYPE.get(event_status, "job_status")

        _ALLOWED_FIELDS = frozenset({
            "job_id", "agent", "bank_code", "status", "error", "result", "timestamp",
        })
        ws_message = {
            "type": event_type,
            **{k: v for k, v in event.items() if k in _ALLOWED_FIELDS},
        }
        try:
            await self._broadcast(ws_message)
        except Exception:
            logger.exception("Failed to broadcast pub/sub event")
