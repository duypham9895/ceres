from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from ceres.api.websocket import ConnectionManager

manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: initialise DB, task runner, arq pool, and pub/sub bridge."""
    from arq import create_pool
    from arq.connections import RedisSettings

    from ceres.api.tasks import CrawlTaskRunner
    from ceres.config import load_config
    from ceres.database import Database
    from ceres.pubsub import PubSubBridge

    config = load_config()
    db = Database(config.database_url)
    await db.connect()

    arq_pool = await create_pool(RedisSettings.from_dsn(config.redis_url))

    task_runner = CrawlTaskRunner(db=db, config=config, arq_pool=arq_pool)
    task_runner.set_broadcast_callback(manager.broadcast)

    pubsub_bridge = PubSubBridge(
        redis_url=config.redis_url,
        broadcast=manager.broadcast,
    )
    await pubsub_bridge.start()

    app.state.db = db
    app.state.config = config
    app.state.task_runner = task_runner

    yield

    await pubsub_bridge.stop()
    await task_runner.cancel_all()
    await arq_pool.close()
    await db.disconnect()


def create_app(use_lifespan: bool = True) -> FastAPI:
    """Create and configure the CERES FastAPI application."""
    app = FastAPI(
        title="CERES API",
        version="0.1.0",
        lifespan=lifespan if use_lifespan else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    from ceres.api.routes import router

    app.include_router(router, prefix="/api")

    @app.websocket("/ws/crawl-status")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("subscribe") == "all":
                    await websocket.send_json({"event": "subscribed"})
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return app


app = create_app()
