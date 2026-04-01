import pytest
from ceres.browser.proxy import NoOpProxyProvider, ProxyProvider
from ceres.utils.captcha import NoOpCaptchaSolver, CaptchaSolver


class TestNoOpProxy:
    @pytest.mark.asyncio
    async def test_get_proxy_returns_none(self):
        provider = NoOpProxyProvider()
        proxy = await provider.get_proxy()
        assert proxy is None

    @pytest.mark.asyncio
    async def test_report_result_is_noop(self):
        provider = NoOpProxyProvider()
        await provider.report_result("http://proxy:8080", True)

    def test_implements_interface(self):
        assert isinstance(NoOpProxyProvider(), ProxyProvider)


class TestNoOpCaptcha:
    @pytest.mark.asyncio
    async def test_solve_returns_none(self):
        solver = NoOpCaptchaSolver()
        result = await solver.solve("recaptcha", "https://example.com")
        assert result is None

    def test_implements_interface(self):
        assert isinstance(NoOpCaptchaSolver(), CaptchaSolver)
