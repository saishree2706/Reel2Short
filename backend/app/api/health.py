"""Health check endpoint."""
from fastapi import APIRouter
from pydantic import BaseModel
import platform
import sys

from ..config import settings

router = APIRouter(prefix="/api/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    environment: str
    python_version: str
    platform: str
    storage_dir: str
    instagram_configured: bool


@router.get("", response_model=HealthResponse)
async def health():
    """Returns application health status."""
    return HealthResponse(
        status="ok",
        environment=settings.APP_ENV,
        python_version=sys.version,
        platform=platform.platform(),
        storage_dir=settings.STORAGE_DIR,
        instagram_configured=bool(settings.INSTAGRAM_ACCESS_TOKEN),
    )

