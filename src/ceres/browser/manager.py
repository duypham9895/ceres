from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any, Optional

from ceres.browser.stealth import STEALTH_ARGS, STEALTH_UA


class BrowserType(str, Enum):
    PLAYWRIGHT = "playwright"
    UNDETECTED = "undetected"


class BrowserManager:
    def __init__(self, proxy: Optional[str] = None):
        self._proxy = proxy

    async def create_context(
        self,
        browser_type: BrowserType = BrowserType.PLAYWRIGHT,
        **kwargs: Any,
    ) -> tuple[Any, Any]:
        if browser_type == BrowserType.PLAYWRIGHT:
            return await self._launch_playwright(**kwargs)
        return await self._launch_undetected(**kwargs)

    async def _launch_playwright(self, **kwargs: Any) -> tuple[Any, Any]:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        launch_args: dict[str, Any] = {"headless": True, "args": STEALTH_ARGS}
        if self._proxy:
            launch_args["proxy"] = {"server": self._proxy}

        browser = await pw.chromium.launch(**launch_args)
        context = await browser.new_context(
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
        return browser, page

    async def _launch_undetected(self, **kwargs: Any) -> tuple[Any, Any]:
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

    async def close_context(
        self, browser: Any, browser_type: BrowserType
    ) -> None:
        if browser_type == BrowserType.PLAYWRIGHT:
            await browser.close()
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, browser.quit)
