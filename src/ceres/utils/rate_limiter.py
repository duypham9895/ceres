from __future__ import annotations

import asyncio
import time
from collections import defaultdict


class RateLimiter:
    """Per-domain rate limiter that enforces a minimum delay between calls."""

    def __init__(self, delay_ms: int = 2000) -> None:
        self._delay_s = delay_ms / 1000.0
        self._last_call: dict[str, float] = defaultdict(float)

    async def wait(self, domain: str = "__default__") -> None:
        now = time.monotonic()
        last = self._last_call[domain]
        elapsed = now - last
        if last > 0 and elapsed < self._delay_s:
            await asyncio.sleep(self._delay_s - elapsed)
        self._last_call[domain] = time.monotonic()
