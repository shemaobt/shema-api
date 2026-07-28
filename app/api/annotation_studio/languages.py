from fastapi import APIRouter

from app.api.annotation_studio._deps import CurrentUser, Db
from app.models.annotation_studio import AsLanguageSummary
from app.services.annotation_studio import dashboard_service

router = APIRouter()


@router.get("/languages", response_model=list[AsLanguageSummary])
async def list_active_languages(db: Db, user: CurrentUser) -> list[AsLanguageSummary]:
    """Tripod languages the user may access that have studio data, with readiness."""
    return await dashboard_service.list_active_languages(db, user)
