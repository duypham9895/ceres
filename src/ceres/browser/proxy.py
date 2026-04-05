"""Proxy providers for browser-based crawling.

Supports three modes:
- NoOpProxyProvider: no proxy (default fallback)
- StaticProxyProvider: single proxy from PROXY_URL env var
- RotatingProxyProvider: round-robin rotation from DB or PROXY_LIST env var
"""

from __future__ import annotations

import logging
import os
import threading
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)

_FAILURE_RATE_THRESHOLD = 0.80


class ProxyProvider(ABC):
    @abstractmethod
    async def get_proxy(self) -> Optional[str]: ...

    @abstractmethod
    async def report_result(self, proxy: str, success: bool) -> None: ...


class NoOpProxyProvider(ProxyProvider):
    async def get_proxy(self) -> Optional[str]:
        return None

    async def report_result(self, proxy: str, success: bool) -> None:
        pass


class StaticProxyProvider(ProxyProvider):
    """Returns the same proxy URL every time."""

    def __init__(self, proxy_url: str) -> None:
        self._proxy_url = proxy_url

    async def get_proxy(self) -> Optional[str]:
        return self._proxy_url

    async def report_result(self, proxy: str, success: bool) -> None:
        pass


class _ProxyStats:
    """Immutable-style tracker for a single proxy's success/failure counts."""

    __slots__ = ("url", "successes", "failures")

    def __init__(self, url: str, successes: int = 0, failures: int = 0) -> None:
        self.url = url
        self.successes = successes
        self.failures = failures

    @property
    def total(self) -> int:
        return self.successes + self.failures

    @property
    def failure_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.failures / self.total

    def with_result(self, success: bool) -> "_ProxyStats":
        """Return a new stats object with the result recorded."""
        if success:
            return _ProxyStats(self.url, self.successes + 1, self.failures)
        return _ProxyStats(self.url, self.successes, self.failures + 1)


class RotatingProxyProvider(ProxyProvider):
    """Round-robin proxy rotation with failure-rate eviction.

    Reads proxies from the ``proxies`` database table on first call.
    Falls back to ``PROXY_LIST`` env var (comma-separated URLs) when
    no database connection is available. Proxies exceeding an 80%
    failure rate are removed from the rotation.
    """

    def __init__(
        self,
        db: Optional[Any] = None,
        initial_urls: Optional[list[str]] = None,
    ) -> None:
        self._db = db
        self._proxies: list[_ProxyStats] = []
        if initial_urls:
            self._proxies = [_ProxyStats(url=u) for u in initial_urls]
        self._index: int = 0
        self._lock = threading.Lock()
        self._loaded = initial_urls is not None

    async def _ensure_loaded(self) -> None:
        """Load proxies from DB or env var on first access."""
        if self._loaded:
            return

        self._loaded = True

        # Try database first
        if self._db is not None:
            try:
                rows = await self._db.pool.fetch(
                    "SELECT proxy_url FROM proxies WHERE status = 'active' ORDER BY rotation_weight DESC"
                )
                if rows:
                    self._proxies = [_ProxyStats(url=r["proxy_url"]) for r in rows]
                    logger.info("Loaded %d proxies from database", len(self._proxies))
                    return
            except Exception:
                logger.warning("Failed to load proxies from database, trying env var")

        # Fall back to PROXY_LIST env var
        proxy_list = os.environ.get("PROXY_LIST", "")
        if proxy_list:
            urls = [u.strip() for u in proxy_list.split(",") if u.strip()]
            self._proxies = [_ProxyStats(url=u) for u in urls]
            logger.info("Loaded %d proxies from PROXY_LIST env var", len(self._proxies))

    async def get_proxy(self) -> Optional[str]:
        await self._ensure_loaded()

        with self._lock:
            if not self._proxies:
                return None

            # Round-robin through available proxies
            start = self._index
            for _ in range(len(self._proxies)):
                proxy = self._proxies[self._index % len(self._proxies)]
                self._index = (self._index + 1) % len(self._proxies)
                if proxy.failure_rate < _FAILURE_RATE_THRESHOLD or proxy.total < 5:
                    return proxy.url

            # All proxies above failure threshold — return the least-bad one
            logger.warning("All proxies exceed failure threshold, returning least-bad")
            best = min(self._proxies, key=lambda p: p.failure_rate)
            return best.url

    async def report_result(self, proxy: str, success: bool) -> None:
        with self._lock:
            updated: list[_ProxyStats] = []
            for stats in self._proxies:
                if stats.url == proxy:
                    new_stats = stats.with_result(success)
                    if new_stats.failure_rate >= _FAILURE_RATE_THRESHOLD and new_stats.total >= 5:
                        logger.warning(
                            "Removing proxy %s (failure rate %.0f%% over %d requests)",
                            proxy,
                            new_stats.failure_rate * 100,
                            new_stats.total,
                        )
                        continue
                    updated.append(new_stats)
                else:
                    updated.append(stats)
            self._proxies = updated


def create_proxy_provider(db: Optional[Any] = None) -> ProxyProvider:
    """Factory: pick the best proxy provider based on available config.

    Priority:
    1. RotatingProxyProvider — if DB has proxies table or PROXY_LIST is set
    2. StaticProxyProvider — if PROXY_URL is set
    3. NoOpProxyProvider — default fallback
    """
    proxy_list = os.environ.get("PROXY_LIST", "")
    proxy_url = os.environ.get("PROXY_URL", "")

    if db is not None or proxy_list:
        return RotatingProxyProvider(db=db)

    if proxy_url:
        return StaticProxyProvider(proxy_url=proxy_url)

    return NoOpProxyProvider()
