from fastapi import APIRouter

from app.core.version import get_app_version
from app.models.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=get_app_version())
