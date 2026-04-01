"""Background task runner for crawl orchestration.

Provides a single-concurrency gate so only one crawl job runs at a time,
with WebSocket broadcasting for real-time progress updates.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, Optional

logger = logging.getLogger(__name__)


class CrawlJobStatus(enum.Enum):
    """Lifecycle states for a crawl job."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True)
class CrawlJob:
    """Immutable snapshot of a crawl job."""

    job_id: str
    agent: str
    status: CrawlJobStatus
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class CrawlTaskRunner:
    """Runs crawl agents with single-concurrency and broadcast support.

    Only one job may execute at a time.  Callers receive ``None`` from
    ``start_job`` when a job is already in progress.
    """

    def __init__(
        self,
        db: Any,
        config: Optional[Any] = None,
    ) -> None:
        self._db = db
        self._config = config
        self._lock = asyncio.Lock()
        self._current_job: Optional[CrawlJob] = None
        self._current_task: Optional[asyncio.Task] = None
        self._broadcast_callback: Optional[
            Callable[[dict], Coroutine[Any, Any, None]]
        ] = None
        self._agent_registry: Dict[str, Callable[..., Coroutine[Any, Any, dict]]] = {}
        self._register_agents()

    # ------------------------------------------------------------------
    # Agent registry
    # ------------------------------------------------------------------

    def _register_agents(self) -> None:
        """Map agent names to their runner coroutines."""
        self._agent_registry = {
            "daily": self._run_daily,
            "scout": self._run_scout,
            "strategist": self._run_strategist,
            "crawler": self._run_crawler,
            "parser": self._run_parser,
            "learning": self._run_learning,
            "lab": self._run_lab,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_job(
        self,
        agent: str,
        bank_code: Optional[str] = None,
    ) -> Optional[CrawlJob]:
        """Start a crawl job if none is currently running.

        Returns the ``CrawlJob`` on success or ``None`` when blocked.
        """
        async with self._lock:
            if self._current_job is not None:
                return None

            agent_fn = self._agent_registry.get(agent)
            if agent_fn is None:
                logger.warning("Unknown agent requested: %s", agent)
                return None

            job_id = str(uuid.uuid4())
            job = CrawlJob(
                job_id=job_id,
                agent=agent,
                status=CrawlJobStatus.RUNNING,
            )
            self._current_job = job
            self._current_task = asyncio.create_task(
                self._execute(job_id, agent, agent_fn, bank_code=bank_code),
            )
            return job

    def get_current_job(self) -> Optional[CrawlJob]:
        """Return the currently running job, or ``None``."""
        return self._current_job

    async def cancel_all(self) -> None:
        """Cancel the current task if one is running."""
        if self._current_task is not None and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass
        self._current_job = None
        self._current_task = None

    def set_broadcast_callback(
        self,
        callback: Callable[[dict], Coroutine[Any, Any, None]],
    ) -> None:
        """Set the WebSocket broadcast function."""
        self._broadcast_callback = callback

    # ------------------------------------------------------------------
    # Internal execution
    # ------------------------------------------------------------------

    async def _execute(
        self,
        job_id: str,
        agent: str,
        agent_fn: Callable[..., Coroutine[Any, Any, dict]],
        **kwargs: Any,
    ) -> None:
        """Run an agent function with broadcasting and cleanup."""
        await self._broadcast(
            {"type": "job_start", "job_id": job_id, "agent": agent},
        )
        try:
            result = await agent_fn(**kwargs)
            await self._broadcast(
                {
                    "type": "job_finish",
                    "job_id": job_id,
                    "agent": agent,
                    "result": result,
                },
            )
        except Exception as exc:
            logger.exception("Job %s failed: %s", job_id, exc)
            await self._broadcast(
                {
                    "type": "job_error",
                    "job_id": job_id,
                    "agent": agent,
                    "error": str(exc),
                },
            )
        finally:
            self._current_job = None
            self._current_task = None

    async def _broadcast(self, message: dict) -> None:
        """Send a message via the broadcast callback if one is set."""
        if self._broadcast_callback is not None:
            try:
                await self._broadcast_callback(message)
            except Exception:
                logger.exception("Broadcast callback failed")

    # ------------------------------------------------------------------
    # Agent runners (lazy imports)
    # ------------------------------------------------------------------

    async def _run_daily(self, **kwargs: Any) -> dict:
        """Run the full daily pipeline: scout -> strategist -> crawler -> parser."""
        job_id = self._current_job.job_id if self._current_job else ""
        results: Dict[str, Any] = {}

        steps = [
            ("scout", self._run_scout),
            ("strategist", self._run_strategist),
            ("crawler", self._run_crawler),
            ("parser", self._run_parser),
        ]
        for step_name, step_fn in steps:
            await self._broadcast(
                {
                    "type": "job_progress",
                    "job_id": job_id,
                    "agent": "daily",
                    "step": step_name,
                },
            )
            step_result = await step_fn(**kwargs)
            results[step_name] = step_result

        return results

    async def _run_scout(self, **kwargs: Any) -> dict:
        from ceres.agents.scout import ScoutAgent

        agent = ScoutAgent(db=self._db, config=self._config)
        return await agent.execute(**kwargs)

    async def _run_strategist(self, **kwargs: Any) -> dict:
        from ceres.agents.strategist import StrategistAgent

        agent = StrategistAgent(db=self._db, config=self._config)
        return await agent.execute(**kwargs)

    async def _run_crawler(self, **kwargs: Any) -> dict:
        from ceres.agents.crawler import CrawlerAgent

        agent = CrawlerAgent(db=self._db, config=self._config)
        return await agent.execute(**kwargs)

    async def _run_parser(self, **kwargs: Any) -> dict:
        from ceres.agents.parser import ParserAgent

        agent = ParserAgent(db=self._db, config=self._config)
        return await agent.execute(**kwargs)

    async def _run_learning(self, **kwargs: Any) -> dict:
        from ceres.agents.learning import LearningAgent

        agent = LearningAgent(db=self._db, config=self._config)
        return await agent.execute(**kwargs)

    async def _run_lab(self, **kwargs: Any) -> dict:
        from ceres.agents.lab import LabAgent

        agent = LabAgent(db=self._db, config=self._config)
        return await agent.execute(**kwargs)
