from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


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
