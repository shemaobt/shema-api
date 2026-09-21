from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user, require_platform_admin
from app.core.database import get_db
from app.core.org_scope import get_managed_project_ids
from app.db.models.auth import User
from app.models.language import (
    LanguageCreate,
    LanguageResponse,
    LanguageStatsResponse,
    LanguageUpdate,
)
from app.services import language_service

router = APIRouter()


@router.get("", response_model=list[LanguageResponse])
async def list_languages(
    include_inactive: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[LanguageResponse]:
    if user.is_platform_admin:
        languages = await language_service.list_languages(
            db, user, include_inactive=include_inactive
        )
    else:
        managed_project_ids = await get_managed_project_ids(db, user.id)
        languages = await language_service.list_languages_by_projects(db, managed_project_ids)
    return [LanguageResponse.model_validate(lang) for lang in languages]


@router.post("", response_model=LanguageResponse, status_code=status.HTTP_201_CREATED)
async def create_language(
    payload: LanguageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LanguageResponse:
    language = await language_service.create_language(
        db, payload.name, payload.code, created_by=str(user.id)
    )
    return LanguageResponse.model_validate(language)


@router.get("/code/{code}", response_model=LanguageResponse)
async def get_language_by_code(
    code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LanguageResponse:
    language = await language_service.get_visible_language_by_code_or_404(db, code, user)
    return LanguageResponse.model_validate(language)


@router.get("/{language_id}", response_model=LanguageResponse)
async def get_language_by_id(
    language_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LanguageResponse:
    language = await language_service.get_visible_language_or_404(db, language_id, user)
    return LanguageResponse.model_validate(language)


@router.delete("/{language_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_language(
    language_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_platform_admin),
) -> None:
    await language_service.deactivate_language(db, language_id, user)


@router.post("/{language_id}/reactivate", response_model=LanguageResponse)
async def reactivate_language(
    language_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_platform_admin),
) -> LanguageResponse:
    language = await language_service.reactivate_language(db, language_id, user)
    return LanguageResponse.model_validate(language)


@router.put("/{language_id}", response_model=LanguageResponse)
async def update_language(
    language_id: str,
    payload: LanguageUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> LanguageResponse:
    language = await language_service.update_language(
        db, language_id, name=payload.name, code=payload.code
    )
    return LanguageResponse.model_validate(language)


@router.get("/{language_id}/stats", response_model=LanguageStatsResponse)
async def get_language_stats(
    language_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> LanguageStatsResponse:
    return await language_service.get_language_stats(db, language_id)
