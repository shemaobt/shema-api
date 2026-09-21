from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user, require_platform_admin
from app.core.database import get_db
from app.db.models.auth import User
from app.models.journey import JourneyCreate, JourneyResponse, JourneyUpdate
from app.services import journey_service

router = APIRouter()


@router.get("", response_model=list[JourneyResponse])
async def list_journeys(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[JourneyResponse]:
    return await journey_service.list_journeys(db)


@router.post("", response_model=JourneyResponse, status_code=status.HTTP_201_CREATED)
async def create_journey(
    payload: JourneyCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> JourneyResponse:
    journey = await journey_service.create_journey(db, payload, created_by=admin.id)
    return await journey_service.get_journey_with_counts(db, journey.id)


@router.get("/{journey_id}", response_model=JourneyResponse)
async def get_journey(
    journey_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JourneyResponse:
    return await journey_service.get_journey_with_counts(db, journey_id)


@router.patch("/{journey_id}", response_model=JourneyResponse)
async def update_journey(
    journey_id: str,
    payload: JourneyUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> JourneyResponse:
    await journey_service.update_journey(db, journey_id, payload)
    return await journey_service.get_journey_with_counts(db, journey_id)


@router.delete("/{journey_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_journey(
    journey_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> None:
    await journey_service.delete_journey(db, journey_id)
