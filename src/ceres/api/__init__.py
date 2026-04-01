from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    """Create and configure the CERES FastAPI application."""
    app = FastAPI(title="CERES API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    from ceres.api.routes import router

    app.include_router(router, prefix="/api")
    return app


app = create_app()
