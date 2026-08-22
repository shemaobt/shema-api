from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user, require_platform_admin
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.models.language import (
    LanguageCreate,
    LanguageProjectRef,
    LanguageResponse,
    LanguageStatsResponse,
)
from app.services import language_service

router = APIRouter()


@router.get("", response_model=list[LanguageResponse])
async def list_languages(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[LanguageResponse]:
    languages = await language_service.list_languages(db)
    return [LanguageResponse.model_validate(lang) for lang in languages]


@router.post("", response_model=LanguageResponse, status_code=status.HTTP_201_CREATED)
async def create_language(
    payload: LanguageCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> LanguageResponse:
    language = await language_service.create_language(db, payload.name, payload.code)
    return LanguageResponse.model_validate(language)


@router.get("/code/{code}", response_model=LanguageResponse)
async def get_language_by_code(
    code: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> LanguageResponse:
    language = await language_service.get_language_by_code(db, code)
    if not language:
        raise NotFoundError("Language not found")
    return LanguageResponse.model_validate(language)


@router.get("/{language_id}", response_model=LanguageResponse)
async def get_language_by_id(
    language_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> LanguageResponse:
    language = await language_service.get_language_or_404(db, language_id)
    return LanguageResponse.model_validate(language)


@router.get("/{language_id}/stats", response_model=LanguageStatsResponse)
async def get_language_stats(
    language_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> LanguageStatsResponse:
    projects = await language_service.get_language_stats(db, language_id)
    return LanguageStatsResponse(
        language_id=language_id,
        project_count=len(projects),
        projects=[LanguageProjectRef(id=project_id, name=name) for project_id, name in projects],
    )
