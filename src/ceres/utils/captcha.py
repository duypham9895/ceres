"""Captcha solving integrations.

Supports:
- NoOpCaptchaSolver: no-op stub (default)
- TwoCaptchaSolver: reCAPTCHA v2 solving via the 2captcha API
"""

from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)

_TWOCAPTCHA_SUBMIT_URL = "https://2captcha.com/in.php"
_TWOCAPTCHA_RESULT_URL = "https://2captcha.com/res.php"
_POLL_INTERVAL_S = 5
_DEFAULT_TIMEOUT_S = 120
_MAX_RETRIES = 2


class CaptchaSolver(ABC):
    @abstractmethod
    async def solve(self, challenge_type: str, page_url: str, **kwargs) -> Optional[str]: ...


class NoOpCaptchaSolver(CaptchaSolver):
    async def solve(self, challenge_type: str, page_url: str, **kwargs) -> Optional[str]:
        return None


class TwoCaptchaSolver(CaptchaSolver):
    """Solves reCAPTCHA v2 challenges via the 2captcha API.

    Submits the sitekey and page URL, then polls for the solution token.
    Uses httpx for async HTTP requests.
    """

    def __init__(self, api_key: str, timeout_s: int = _DEFAULT_TIMEOUT_S) -> None:
        self._api_key = api_key
        self._timeout_s = timeout_s

    async def solve(self, challenge_type: str, page_url: str, **kwargs) -> Optional[str]:
        """Solve a captcha challenge.

        Args:
            challenge_type: Type of captcha (only "recaptcha_v2" supported).
            page_url: The URL of the page with the captcha.
            **kwargs: Additional params, e.g. ``sitekey`` for reCAPTCHA.

        Returns:
            Solution token string, or None on failure.
        """
        if challenge_type != "recaptcha_v2":
            logger.warning("Unsupported captcha type: %s", challenge_type)
            return None

        sitekey = kwargs.get("sitekey")
        if not sitekey:
            logger.error("sitekey is required for reCAPTCHA v2 solving")
            return None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                return await self._solve_recaptcha_v2(sitekey, page_url)
            except Exception:
                logger.exception(
                    "2captcha attempt %d/%d failed for %s",
                    attempt,
                    _MAX_RETRIES,
                    page_url,
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(2)

        return None

    async def _solve_recaptcha_v2(self, sitekey: str, page_url: str) -> Optional[str]:
        """Submit reCAPTCHA v2 task and poll for result."""
        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: Submit the captcha
            submit_resp = await client.post(
                _TWOCAPTCHA_SUBMIT_URL,
                data={
                    "key": self._api_key,
                    "method": "userrecaptcha",
                    "googlekey": sitekey,
                    "pageurl": page_url,
                    "json": "1",
                },
            )
            submit_data = submit_resp.json()

            if submit_data.get("status") != 1:
                logger.error("2captcha submit failed: %s", submit_data.get("request"))
                return None

            task_id = submit_data["request"]
            logger.info("2captcha task submitted: %s", task_id)

            # Step 2: Poll for result
            elapsed = 0
            await asyncio.sleep(_POLL_INTERVAL_S)
            elapsed += _POLL_INTERVAL_S

            while elapsed < self._timeout_s:
                result_resp = await client.get(
                    _TWOCAPTCHA_RESULT_URL,
                    params={
                        "key": self._api_key,
                        "action": "get",
                        "id": task_id,
                        "json": "1",
                    },
                )
                result_data = result_resp.json()

                if result_data.get("status") == 1:
                    logger.info("2captcha solved task %s", task_id)
                    return result_data["request"]

                if result_data.get("request") != "CAPCHA_NOT_READY":
                    logger.error("2captcha error: %s", result_data.get("request"))
                    return None

                await asyncio.sleep(_POLL_INTERVAL_S)
                elapsed += _POLL_INTERVAL_S

            logger.error("2captcha timeout after %ds for task %s", self._timeout_s, task_id)
            return None


def create_captcha_solver() -> CaptchaSolver:
    """Factory: return TwoCaptchaSolver if API key is set, else NoOpCaptchaSolver."""
    api_key = os.environ.get("TWOCAPTCHA_API_KEY", "")
    if api_key:
        logger.info("2captcha solver enabled")
        return TwoCaptchaSolver(api_key=api_key)
    return NoOpCaptchaSolver()
