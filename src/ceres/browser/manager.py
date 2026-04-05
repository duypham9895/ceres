"""Browser manager with shared Playwright instance and concurrency control.

Key design decisions:
- ONE Playwright server process, reused for all crawls (prevents process leak)
- Lightweight browser contexts (not full browsers) per page fetch (~10MB vs ~300MB)
- Semaphore caps concurrent browser contexts to prevent OOM
- Proper cleanup via async context manager and explicit start/stop lifecycle
"""

from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Any, Optional

from ceres.browser.stealth import STEALTH_ARGS, STEALTH_UA

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONTEXTS = 5


class BrowserType(str, Enum):
    PLAYWRIGHT = "playwright"
    UNDETECTED = "undetected"


class BrowserManager:
    """Shared browser resource manager with concurrency control.

    Usage:
        manager = BrowserManager(max_contexts=5)
        await manager.start()
        try:
            browser, page = await manager.create_context(BrowserType.PLAYWRIGHT)
            ...
            await manager.close_context(browser, BrowserType.PLAYWRIGHT)
        finally:
            await manager.stop()
    """

    def __init__(
        self,
        *,
        max_contexts: int = DEFAULT_MAX_CONTEXTS,
        proxy: Optional[str] = None,
    ) -> None:
        self._max_contexts = max_contexts
        self._proxy = proxy
        self._semaphore = asyncio.Semaphore(max_contexts)
        self._pw: Any = None  # Playwright instance (single, long-lived)
        self._browser: Any = None  # Shared Chromium browser (single, long-lived)
        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Launch the shared Playwright instance and browser.

        Call once at app startup. Safe to call multiple times (idempotent).
        """
        if self._started:
            return

        from playwright.async_api import async_playwright as _async_pw

        self._pw = await _async_pw().start()

        launch_args: dict[str, Any] = {"headless": True, "args": STEALTH_ARGS}
        if self._proxy:
            launch_args["proxy"] = {"server": self._proxy}

        self._browser = await self._pw.chromium.launch(**launch_args)
        self._started = True
        logger.info(
            "BrowserManager started: 1 Playwright instance, max %d contexts",
            self._max_contexts,
        )

    async def stop(self) -> None:
        """Shut down the shared browser and Playwright instance.

        Call once at app shutdown. Safe to call multiple times (idempotent).
        """
        if not self._started:
            return

        try:
            if self._browser is not None:
                await self._browser.close()
                self._browser = None
        except Exception:
            logger.warning("Error closing shared browser", exc_info=True)

        try:
            if self._pw is not None:
                await self._pw.stop()
                self._pw = None
        except Exception:
            logger.warning("Error stopping Playwright", exc_info=True)

        self._started = False
        logger.info("BrowserManager stopped")

    # ------------------------------------------------------------------
    # Context creation (concurrency-gated)
    # ------------------------------------------------------------------

    async def create_context(
        self,
        browser_type: BrowserType = BrowserType.PLAYWRIGHT,
        **kwargs: Any,
    ) -> tuple[Any, Any]:
        """Create a browser context + page, waiting for a semaphore slot.

        For Playwright: returns (context, page) using the shared browser.
        For Undetected: returns (driver, driver) — each gets its own process.

        The caller MUST call close_context() when done (use try/finally).
        """
        await self._semaphore.acquire()
        try:
            if browser_type == BrowserType.PLAYWRIGHT:
                return await self._create_playwright_context(**kwargs)
            return await self._create_undetected_context(**kwargs)
        except BaseException:
            self._semaphore.release()
            raise

    async def _create_playwright_context(self, **kwargs: Any) -> tuple[Any, Any]:
        """Create a lightweight context on the shared browser."""
        if not self._started or self._browser is None:
            await self.start()

        context = await self._browser.new_context(
            user_agent=STEALTH_UA,
            viewport={"width": 1920, "height": 1080},
            java_script_enabled=True,
        )
        await context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
            """
        )
        page = await context.new_page()
        return context, page

    async def _create_undetected_context(self, **kwargs: Any) -> tuple[Any, Any]:
        """Launch an undetected-chromedriver instance (own process, gated by semaphore)."""
        import undetected_chromedriver as uc

        loop = asyncio.get_event_loop()
        options = uc.ChromeOptions()
        options.add_argument("--headless=new")
        for arg in STEALTH_ARGS:
            options.add_argument(arg)
        if self._proxy:
            options.add_argument(f"--proxy-server={self._proxy}")

        driver = await loop.run_in_executor(
            None, lambda: uc.Chrome(options=options)
        )
        return driver, driver

    # ------------------------------------------------------------------
    # Context cleanup
    # ------------------------------------------------------------------

    async def close_context(
        self, context: Any, browser_type: BrowserType
    ) -> None:
        """Close a browser context/driver and release the semaphore slot.

        Always call this in a finally block after create_context().
        """
        try:
            if browser_type == BrowserType.PLAYWRIGHT:
                await context.close()
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, context.quit)
        except Exception:
            logger.warning("Error closing browser context", exc_info=True)
        finally:
            self._semaphore.release()
