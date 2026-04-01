from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class CaptchaSolver(ABC):
    @abstractmethod
    async def solve(self, challenge_type: str, page_url: str) -> Optional[str]: ...


class NoOpCaptchaSolver(CaptchaSolver):
    async def solve(self, challenge_type: str, page_url: str) -> Optional[str]:
        return None
