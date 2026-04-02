"""arq worker module for CERES — agent task runner with Redis pub/sub events."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional, Type

from arq.connections import RedisSettings

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
    agent = agent_class(db=db, config=config)

    kwargs: dict[str, Any] = {}
    if bank_code is not None:
        kwargs["bank_code"] = bank_code
    if force:
        kwargs["force"] = force

    try:
        result = await agent.execute(**kwargs)
    except Exception as exc:
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
    """arq startup hook — create DB connection and load config."""
    config = load_config()
    db = Database(config.database_url)
    await db.connect()
    ctx["db"] = db
    ctx["config"] = config
    logger.info("Worker started: DB connected")


async def shutdown(ctx: dict) -> None:
    """arq shutdown hook — close DB connection."""
    db: Database = ctx.get("db")
    if db is not None:
        await db.disconnect()
    logger.info("Worker stopped: DB disconnected")


# ---------------------------------------------------------------------------
# arq WorkerSettings
# ---------------------------------------------------------------------------

_redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379")
_max_jobs: int = int(os.environ.get("CERES_MAX_WORKERS", "3"))

# Parse redis URL into RedisSettings
_redis_parts = _redis_url.replace("redis://", "").split(":")
_redis_host = _redis_parts[0] if _redis_parts else "localhost"
_redis_port = int(_redis_parts[1]) if len(_redis_parts) > 1 else 6379


class WorkerSettings:
    """arq worker configuration."""

    functions = [run_agent_task]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = _max_jobs
    job_timeout = 600
    max_tries = 3
    redis_settings = RedisSettings(host=_redis_host, port=_redis_port)
