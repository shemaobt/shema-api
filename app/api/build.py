from fastapi import APIRouter, Response

from app.core.config import get_settings
from app.models.build import BuildResponse, MinimumApp
from app.services.internalization_room.llm import classifier_ladder, voice_ladder

router = APIRouter()


@router.get("/version", response_model=BuildResponse)
async def build(response: Response) -> BuildResponse:
    response.headers["Cache-Control"] = "no-store"
    settings = get_settings()
    return BuildResponse(
        build=settings.build_id,
        store=f"gcs:{settings.gcs_platform_bucket}",
        model=voice_ladder(settings),
        classifier_model=classifier_ladder(settings),
        minimum_app=MinimumApp(
            ios=settings.internalization_room_minimum_app_ios,
            android=settings.internalization_room_minimum_app_android,
        ),
    )
