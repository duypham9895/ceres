import asyncio
import time
import pytest
from ceres.utils.rate_limiter import RateLimiter

class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_first_call_not_delayed(self):
        limiter = RateLimiter(delay_ms=1000)
        start = time.monotonic()
        await limiter.wait()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_second_call_delayed(self):
        limiter = RateLimiter(delay_ms=200)
        await limiter.wait()
        start = time.monotonic()
        await limiter.wait()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.15

    @pytest.mark.asyncio
    async def test_per_domain_isolation(self):
        limiter = RateLimiter(delay_ms=500)
        await limiter.wait(domain="a.com")
        start = time.monotonic()
        await limiter.wait(domain="b.com")
        elapsed = time.monotonic() - start
        assert elapsed < 0.1
