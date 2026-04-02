"""Background task runner for crawl orchestration.

Provides a single-concurrency gate so only one crawl job runs at a time,
with WebSocket broadcasting for real-time progress updates.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import os
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
        arq_pool: Optional[Any] = None,
    ) -> None:
        self._db = db
        self._config = config
        self._arq_pool = arq_pool
        self._lock = asyncio.Lock()
        self._current_job: Optional[CrawlJob] = None
        self._current_task: Optional[asyncio.Task] = None
        self._broadcast_callback: Optional[
            Callable[[dict], Coroutine[Any, Any, None]]
        ] = None
        self._current_step: Optional[str] = None
        self._step_index: int = 0
        self._total_steps: int = 0
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
        force: bool = False,
    ) -> Optional[CrawlJob]:
        """Start a crawl job, dispatching to arq or running in-process.

        When an ``arq_pool`` was provided at construction time the job is
        enqueued to the distributed worker and returned immediately with
        ``QUEUED`` status.  Otherwise the legacy single-concurrency
        in-process path is used (returns ``None`` when blocked).
        """
        if self._arq_pool is not None:
            return await self._enqueue_job(agent, bank_code=bank_code, force=force)
        return await self._start_job_inprocess(agent, bank_code=bank_code, force=force)

    async def _enqueue_job(
        self,
        agent: str,
        bank_code: Optional[str] = None,
        force: bool = False,
    ) -> CrawlJob:
        """Enqueue a job to arq. No concurrency gate."""
        job_id = str(uuid.uuid4())
        await self._arq_pool.enqueue_job(
            "run_agent_task",
            job_id=job_id,
            agent_name=agent,
            bank_code=bank_code,
            force=force,
        )
        return CrawlJob(job_id=job_id, agent=agent, status=CrawlJobStatus.QUEUED)

    async def _start_job_inprocess(
        self,
        agent: str,
        bank_code: Optional[str] = None,
        force: bool = False,
    ) -> Optional[CrawlJob]:
        """Run a job in-process with single-concurrency lock (legacy fallback)."""
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

    def get_step_info(self) -> Optional[dict]:
        """Return current pipeline step tracking info, or None if not a pipeline run."""
        if self._total_steps == 0:
            return None
        return {
            "current_step": self._current_step,
            "step_index": self._step_index,
            "total_steps": self._total_steps,
        }

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
        # Log agent run start (guarded — logging failure must not crash the agent)
        run_id: Optional[str] = None
        try:
            run_row = await self._db.log_agent_start(agent_name=agent)
            run_id = str(run_row["id"])
        except Exception:
            logger.warning("Failed to log agent start for %s", agent)

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
            if run_id is not None:
                try:
                    await self._db.log_agent_finish(
                        run_id=run_id, result=result,
                    )
                except Exception:
                    logger.warning("Failed to log agent finish for %s", agent)
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
            if run_id is not None:
                try:
                    await self._db.log_agent_error(
                        run_id=run_id, error_message=str(exc),
                    )
                except Exception:
                    logger.warning("Failed to log agent error for %s", agent)
        finally:
            self._current_job = None
            self._current_task = None
            self._current_step = None
            self._step_index = 0
            self._total_steps = 0

    async def _broadcast(self, message: dict) -> None:
        """Send a message via the broadcast callback if one is set."""
        if self._broadcast_callback is not None:
            try:
                await self._broadcast_callback(message)
            except Exception:
                logger.exception("Broadcast callback failed")

    @staticmethod
    def _normalize_result(result: dict, agent_name: str) -> dict:
        """Add standardized bank count fields to agent results without mutation."""
        if "banks_processed" in result:
            return result

        if agent_name == "scout":
            return {
                **result,
                "banks_processed": result.get("banks_checked", 0),
                "banks_total": result.get("banks_checked", 0),
                "banks_failed": result.get("unreachable", 0) + result.get("blocked", 0),
            }
        if agent_name == "crawler":
            return {
                **result,
                "banks_processed": result.get("banks_crawled", 0),
                "banks_total": result.get("banks_crawled", 0) + result.get("banks_failed", 0),
                "banks_failed": result.get("banks_failed", 0),
            }
        if agent_name == "parser":
            return {
                **result,
                "banks_processed": result.get("programs_parsed", 0),
                "banks_total": result.get("programs_parsed", 0) + len(result.get("errors", [])),
                "banks_failed": len(result.get("errors", [])),
            }
        return {**result, "banks_processed": 0, "banks_total": 0, "banks_failed": 0}

    # ------------------------------------------------------------------
    # Agent runners (lazy imports)
    # ------------------------------------------------------------------

    async def _run_daily(self, **kwargs: Any) -> dict:
        """Run the full daily pipeline: scout -> strategist -> crawler (+ parse) -> learning."""
        job_id = self._current_job.job_id if self._current_job else ""
        results: Dict[str, Any] = {}

        steps = [
            ("scout", self._run_scout),
            ("strategist", self._run_strategist),
            ("crawler", self._run_crawler),
            ("learning", self._run_learning),
        ]
        n_steps = len(steps)
        self._total_steps = n_steps

        for i, (step_name, step_fn) in enumerate(steps):
            self._current_step = step_name
            self._step_index = i

            await self._broadcast({
                "type": "job_step_start",
                "job_id": job_id,
                "agent": "daily",
                "step": step_name,
                "step_index": i,
                "total_steps": n_steps,
            })

            step_result = await step_fn(**kwargs)
            step_result = self._normalize_result(step_result, step_name)
            results[step_name] = step_result

            await self._broadcast({
                "type": "job_progress",
                "job_id": job_id,
                "agent": "daily",
                "step": step_name,
                "step_index": i,
                "total_steps": n_steps,
                "banks_processed": step_result.get("banks_processed", 0),
                "banks_total": step_result.get("banks_total", 0),
                "banks_failed": step_result.get("banks_failed", 0),
            })

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
        """Crawl pages then immediately parse them with the LLM extractor."""
        from ceres.agents.crawler import CrawlerAgent

        crawl_result = await CrawlerAgent(db=self._db, config=self._config).execute(**kwargs)

        if crawl_result.get("pages_fetched", 0) > 0:
            parse_result = await self._run_parser(**kwargs)
            crawl_result["programs_parsed"] = parse_result.get("programs_parsed", 0)
        else:
            crawl_result["programs_parsed"] = 0

        return crawl_result

    async def _run_parser(self, **kwargs: Any) -> dict:
        from ceres.agents.parser import ParserAgent
        from ceres.extractors.llm import ClaudeLLMExtractor, MiniMaxLLMExtractor

        llm_extractor = None

        # Try MiniMax first (primary), then Anthropic as fallback
        minimax_key = os.environ.get("MINIMAX_API_KEY")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

        if minimax_key:
            llm_extractor = MiniMaxLLMExtractor(api_key=minimax_key)
        elif anthropic_key:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=anthropic_key)
            llm_extractor = ClaudeLLMExtractor(client=client)

        agent = ParserAgent(
            db=self._db, config=self._config, llm_extractor=llm_extractor,
        )
        return await agent.execute(**kwargs)

    async def _run_learning(self, **kwargs: Any) -> dict:
        from ceres.agents.learning import LearningAgent

        agent = LearningAgent(db=self._db, config=self._config)
        return await agent.execute(**kwargs)

    async def _run_lab(self, **kwargs: Any) -> dict:
        from ceres.agents.lab import LabAgent

        agent = LabAgent(db=self._db, config=self._config)
        return await agent.execute(**kwargs)
