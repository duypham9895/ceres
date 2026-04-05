import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ceres.browser.manager import BrowserManager, BrowserType
from ceres.browser.stealth import detect_anti_bot, AntiBotResult


class TestBrowserManagerLifecycle:
    """Tests for the shared BrowserManager lifecycle and concurrency control."""

    @pytest.mark.asyncio
    async def test_start_creates_single_playwright_instance(self):
        """start() should launch exactly one Playwright + one browser."""
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.add_init_script = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        mock_pw = AsyncMock()
        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_pw_cm = AsyncMock()
        mock_pw_cm.start = AsyncMock(return_value=mock_pw)

        with patch(
            "playwright.async_api.async_playwright",
            return_value=mock_pw_cm,
        ):
            manager = BrowserManager(max_contexts=3)
            await manager.start()

            assert manager._started is True
            mock_pw_cm.start.assert_called_once()
            mock_pw.chromium.launch.assert_called_once()

            await manager.stop()
            assert manager._started is False

    @pytest.mark.asyncio
    async def test_stop_calls_pw_stop(self):
        """stop() must call pw.stop() to kill the Node.js subprocess."""
        mock_browser = AsyncMock()
        mock_pw = AsyncMock()

        manager = BrowserManager(max_contexts=2)
        manager._pw = mock_pw
        manager._browser = mock_browser
        manager._started = True

        await manager.stop()

        mock_browser.close.assert_called_once()
        mock_pw.stop.assert_called_once()
        assert manager._started is False

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self):
        """Calling start() twice should not create a second Playwright instance."""
        mock_pw_cm = AsyncMock()
        mock_pw = AsyncMock()
        mock_pw.chromium.launch = AsyncMock(return_value=AsyncMock())
        mock_pw_cm.start = AsyncMock(return_value=mock_pw)

        with patch(
            "playwright.async_api.async_playwright",
            return_value=mock_pw_cm,
        ):
            manager = BrowserManager(max_contexts=2)
            await manager.start()
            await manager.start()  # second call should be no-op

            assert mock_pw_cm.start.call_count == 1

            await manager.stop()

    @pytest.mark.asyncio
    async def test_semaphore_caps_concurrency(self):
        """create_context should block when max_contexts are in use."""
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.add_init_script = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        manager = BrowserManager(max_contexts=1)
        manager._pw = AsyncMock()
        manager._browser = mock_browser
        manager._started = True

        # Acquire the one allowed slot
        ctx1, page1 = await manager.create_context(BrowserType.PLAYWRIGHT)

        # Second create should block (timeout quickly to prove it)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                manager.create_context(BrowserType.PLAYWRIGHT),
                timeout=0.1,
            )

        # Release the slot
        await manager.close_context(ctx1, BrowserType.PLAYWRIGHT)

        # Now it should succeed
        ctx2, page2 = await manager.create_context(BrowserType.PLAYWRIGHT)
        await manager.close_context(ctx2, BrowserType.PLAYWRIGHT)

    @pytest.mark.asyncio
    async def test_close_context_releases_semaphore_on_error(self):
        """close_context releases the semaphore even if context.close() raises."""
        mock_context = AsyncMock()
        mock_context.close = AsyncMock(side_effect=RuntimeError("close failed"))

        manager = BrowserManager(max_contexts=1)
        manager._semaphore = asyncio.Semaphore(1)

        # Simulate an acquired slot
        await manager._semaphore.acquire()

        # close_context should release despite the error
        await manager.close_context(mock_context, BrowserType.PLAYWRIGHT)

        # Semaphore should be available again
        assert not manager._semaphore.locked()

    @pytest.mark.asyncio
    async def test_create_context_releases_semaphore_on_launch_failure(self):
        """If context creation fails, the semaphore slot must be released."""
        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(side_effect=RuntimeError("launch failed"))

        manager = BrowserManager(max_contexts=1)
        manager._pw = AsyncMock()
        manager._browser = mock_browser
        manager._started = True

        with pytest.raises(RuntimeError, match="launch failed"):
            await manager.create_context(BrowserType.PLAYWRIGHT)

        # Semaphore should still be available
        assert not manager._semaphore.locked()


class TestBrowserManagerLegacy:
    """Preserve existing test coverage for create/close context."""

    @pytest.mark.asyncio
    async def test_create_playwright_context(self):
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.add_init_script = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        manager = BrowserManager(max_contexts=5)
        manager._pw = AsyncMock()
        manager._browser = mock_browser
        manager._started = True

        ctx, page = await manager.create_context(BrowserType.PLAYWRIGHT)
        assert page is mock_page
        await manager.close_context(ctx, BrowserType.PLAYWRIGHT)

    @pytest.mark.asyncio
    async def test_close_playwright_context(self):
        mock_context = AsyncMock()
        manager = BrowserManager(max_contexts=5)
        # Pre-acquire semaphore to simulate create_context
        await manager._semaphore.acquire()

        await manager.close_context(mock_context, BrowserType.PLAYWRIGHT)
        mock_context.close.assert_called_once()


class TestAntiBotDetection:
    def test_detect_cloudflare(self):
        html = '<div class="cf-browser-verification">Checking your browser</div>'
        result = detect_anti_bot(html)
        assert result.detected is True
        assert result.anti_bot_type == "cloudflare"

    def test_detect_recaptcha(self):
        html = '<div class="g-recaptcha" data-sitekey="xxx"></div>'
        result = detect_anti_bot(html)
        assert result.detected is True
        assert result.anti_bot_type == "recaptcha"

    def test_no_anti_bot(self):
        html = "<html><body><h1>Welcome to Bank XYZ</h1></body></html>"
        result = detect_anti_bot(html)
        assert result.detected is False

    def test_detect_datadome(self):
        html = '<script src="https://js.datadome.co/tags.js"></script>'
        result = detect_anti_bot(html)
        assert result.detected is True
        assert result.anti_bot_type == "datadome"
