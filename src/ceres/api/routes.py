from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def health_check() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok"}
