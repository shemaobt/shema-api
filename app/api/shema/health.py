from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.shema import ShemaHealthResponse
from app.services.shema import get_module_status

router = APIRouter()


@router.get("/health", response_model=ShemaHealthResponse)
async def shema_health(db: AsyncSession = Depends(get_db)) -> ShemaHealthResponse:
    return await get_module_status(db)
