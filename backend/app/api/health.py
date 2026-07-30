from typing import Any

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health check")
async def health_check() -> dict[str, Any]:
    """Health check endpoint to verify system status and version."""
    return {"status": "ok", "version": settings.APP_VERSION}
