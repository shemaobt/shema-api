from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user, require_platform_admin
from app.core.database import get_db
from app.db.models.auth import User
from app.models.journey import (
    PhaseCategoryCreate,
    PhaseCategoryResponse,
    PhaseCategoryUpdate,
)
from app.services import phase_category_service

router = APIRouter()


@router.get("", response_model=list[PhaseCategoryResponse])
async def list_phase_categories(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PhaseCategoryResponse]:
    return await phase_category_service.list_phase_categories(db)


@router.post("", response_model=PhaseCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_phase_category(
    payload: PhaseCategoryCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> PhaseCategoryResponse:
    category = await phase_category_service.create_phase_category(db, payload)
    return PhaseCategoryResponse(
        id=category.id,
        name=category.name,
        color=category.color,
        icon=category.icon,
        phase_count=0,
    )


@router.patch("/{category_id}", response_model=PhaseCategoryResponse)
async def update_phase_category(
    category_id: str,
    payload: PhaseCategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> PhaseCategoryResponse:
    await phase_category_service.update_phase_category(db, category_id, payload)
    return await phase_category_service.get_phase_category_with_count(db, category_id)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_phase_category(
    category_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> None:
    await phase_category_service.delete_phase_category(db, category_id)
