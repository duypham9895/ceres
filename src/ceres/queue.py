"""arq worker module for CERES — agent task runner with Redis pub/sub events."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional, Type

from arq.connections import RedisSettings
from arq.cron import cron

from ceres.config import load_config
from ceres.database import Database

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHANNEL = "ceres:job_events"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event(
    *,
    job_id: str,
    agent: str,
    bank_code: Optional[str],
    status: str,
    error: Optional[str],
    result: Optional[Any],
) -> bytes:
    """Build a JSON-encoded event payload as bytes."""
    payload = {
        "job_id": job_id,
        "agent": agent,
        "bank_code": bank_code,
        "status": status,
        "error": error,
        "result": result,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
    return json.dumps(payload).encode()


def _get_agent_class(agent_name: str) -> Type:
    """Lazy-import and return the agent class for the given agent name.

    Raises ValueError for unknown or unsupported agents.
    """
    if agent_name == "parser":
        raise ValueError(
            "parser agent requires special llm_extractor setup and cannot be "
            "dispatched via the generic job queue."
        )

    _registry: dict[str, tuple[str, str]] = {
        "scout": ("ceres.agents.scout", "ScoutAgent"),
        "strategist": ("ceres.agents.strategist", "StrategistAgent"),
        "crawler": ("ceres.agents.crawler", "CrawlerAgent"),
        "learning": ("ceres.agents.learning", "LearningAgent"),
        "lab": ("ceres.agents.lab", "LabAgent"),
    }

    if agent_name not in _registry:
        raise ValueError(
            f"Unknown agent '{agent_name}'. "
            f"Valid agents: {sorted(_registry.keys())}."
        )

    module_path, class_name = _registry[agent_name]
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


# ---------------------------------------------------------------------------
# arq task
# ---------------------------------------------------------------------------


async def run_agent_task(
    ctx: dict,
    *,
    job_id: str,
    agent_name: str,
    bank_code: Optional[str] = None,
    force: bool = False,
) -> dict:
    """arq task that instantiates and runs a CERES agent.

    Publishes "running" before execution and "success" or "error" after.
    """
    redis = ctx["redis"]
    db: Database = ctx["db"]
    config = ctx["config"]

    # Log agent run start to database
    run_id: Optional[str] = None
    try:
        run_row = await db.log_agent_start(agent_name=agent_name, job_id=job_id)
        run_id = str(run_row["id"])
    except Exception:
        logger.warning("Failed to log agent start for %s (job %s)", agent_name, job_id)

    await redis.publish(
        CHANNEL,
        _event(
            job_id=job_id,
            agent=agent_name,
            bank_code=bank_code,
            status="running",
            error=None,
            result=None,
        ),
    )

    agent_class = _get_agent_class(agent_name)
    kwargs_init: dict[str, Any] = {"db": db, "config": config}
    if agent_name == "crawler" and "browser_manager" in ctx:
        kwargs_init["browser_manager"] = ctx["browser_manager"]
    agent = agent_class(**kwargs_init)

    kwargs: dict[str, Any] = {}
    if bank_code is not None:
        kwargs["bank_code"] = bank_code
    if force:
        kwargs["force"] = force

    try:
        result = await agent.execute(**kwargs)
    except BaseException as exc:
        # Log failure to database
        if run_id is not None:
            try:
                await db.log_agent_error(run_id=run_id, error_message=str(exc))
            except Exception:
                logger.warning("Failed to log agent error for %s", agent_name)

        await redis.publish(
            CHANNEL,
            _event(
                job_id=job_id,
                agent=agent_name,
                bank_code=bank_code,
                status="error",
                error=str(exc),
                result=None,
            ),
        )
        raise

    # Log success to database
    if run_id is not None:
        try:
            await db.log_agent_finish(run_id=run_id, result=result or {})
        except Exception:
            logger.warning("Failed to log agent finish for %s", agent_name)

    await redis.publish(
        CHANNEL,
        _event(
            job_id=job_id,
            agent=agent_name,
            bank_code=bank_code,
            status="success",
            error=None,
            result=result,
        ),
    )

    return result


# ---------------------------------------------------------------------------
# Worker lifecycle hooks
# ---------------------------------------------------------------------------


async def startup(ctx: dict) -> None:
    """arq startup hook — create DB connection, load config, start browser manager."""
    from ceres.browser.manager import BrowserManager

    config = load_config()
    db = Database(config.database_url)
    await db.connect()

    browser_manager = BrowserManager(
        max_contexts=int(os.environ.get("CERES_MAX_WORKERS", "3")),
    )
    await browser_manager.start()

    ctx["db"] = db
    ctx["config"] = config
    ctx["browser_manager"] = browser_manager
    logger.info("Worker started: DB connected, browser manager ready")


async def shutdown(ctx: dict) -> None:
    """arq shutdown hook — close browser manager and DB connection."""
    browser_manager = ctx.get("browser_manager")
    if browser_manager is not None:
        await browser_manager.stop()

    db: Database = ctx.get("db")
    if db is not None:
        await db.disconnect()
    logger.info("Worker stopped: browser manager and DB disconnected")


# ---------------------------------------------------------------------------
# Scheduled daily pipeline
# ---------------------------------------------------------------------------


async def run_daily_pipeline(ctx: dict) -> dict:
    """Cron task that runs the full daily pipeline: scout -> strategist -> crawler -> learning.

    Each step is dispatched as an arq job and awaited sequentially.
    """
    import uuid

    db: Database = ctx["db"]
    config = ctx["config"]
    redis = ctx["redis"]

    steps = ["scout", "strategist", "crawler", "learning"]
    results: dict = {}

    for step_name in steps:
        job_id = str(uuid.uuid4())
        logger.info("Daily pipeline: starting %s (job %s)", step_name, job_id)

        try:
            step_result = await run_agent_task(
                ctx,
                job_id=job_id,
                agent_name=step_name,
            )
            results = {**results, step_name: step_result}
        except Exception as exc:
            logger.error("Daily pipeline: %s failed: %s", step_name, exc)
            results = {**results, step_name: {"error": str(exc)}}
            break

    logger.info("Daily pipeline complete: %s", list(results.keys()))
    return results


# ---------------------------------------------------------------------------
# arq WorkerSettings
# ---------------------------------------------------------------------------

_redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379")
_max_jobs: int = int(os.environ.get("CERES_MAX_WORKERS", "3"))
_max_retries: int = int(os.environ.get("CERES_MAX_RETRIES", "3"))


class WorkerSettings:
    """arq worker configuration."""

    functions = [run_agent_task]
    cron_jobs = [
        cron(run_daily_pipeline, hour=2, minute=0),
    ]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = _max_jobs
    job_timeout = 600
    max_tries = _max_retries
    redis_settings = RedisSettings.from_dsn(_redis_url)
