import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ceres.browser.manager import BrowserManager, BrowserType
from ceres.browser.stealth import detect_anti_bot, AntiBotResult


class TestBrowserManager:
    @pytest.mark.asyncio
    async def test_create_playwright_context(self):
        manager = BrowserManager()
        with patch.object(manager, "_launch_playwright", new_callable=AsyncMock) as mock:
            mock.return_value = (AsyncMock(), AsyncMock())
            browser, page = await manager.create_context(BrowserType.PLAYWRIGHT)
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_undetected_context(self):
        manager = BrowserManager()
        with patch.object(manager, "_launch_undetected", new_callable=AsyncMock) as mock:
            mock.return_value = (MagicMock(), MagicMock())
            browser, page = await manager.create_context(BrowserType.UNDETECTED)
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_playwright_context(self):
        manager = BrowserManager()
        browser = AsyncMock()
        await manager.close_context(browser, BrowserType.PLAYWRIGHT)
        browser.close.assert_called_once()


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
