"""Base agent ABC with execution wrapper for CERES agents."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from ceres.database import Database


class BaseAgent(ABC):
    """Abstract base class for all CERES agents.

    Subclasses must define ``name`` and implement the ``run`` method.
    The ``execute`` wrapper adds logging and timing around each run.
    """

    name: str = "base"

    def __init__(self, db: Database, config: Optional[Any] = None) -> None:
        self.db = db
        self.config = config
        self.logger = logging.getLogger(f"ceres.agents.{self.name}")

    @abstractmethod
    async def run(self, **kwargs) -> dict:
        ...

    async def execute(self, **kwargs) -> dict:
        """Run the agent with logging and timing."""
        self.logger.info(f"[{self.name}] Starting execution")
        start = time.monotonic()
        try:
            result = await self.run(**kwargs)
            elapsed = time.monotonic() - start
            self.logger.info(f"[{self.name}] Completed in {elapsed:.1f}s")
            return result
        except Exception as e:
            elapsed = time.monotonic() - start
            self.logger.error(f"[{self.name}] Failed after {elapsed:.1f}s: {e}")
            raise
