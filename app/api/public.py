from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.public_request import (
    PublicLanguageOption,
    PublicLanguageRequestCreate,
    PublicProjectRequestCreate,
    PublicRequestResponse,
)
from app.services import language_service, public_request_service

router = APIRouter()


@router.get("/languages", response_model=list[PublicLanguageOption])
@limiter.limit("30/minute")
async def list_public_languages(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> list[PublicLanguageOption]:
    languages = await language_service.list_languages(db)
    return [PublicLanguageOption.model_validate(lang) for lang in languages]


@router.post(
    "/requests/language",
    response_model=PublicRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute;20/hour")
async def request_language_creation(
    request: Request,
    payload: PublicLanguageRequestCreate,
    db: AsyncSession = Depends(get_db),
) -> PublicRequestResponse:
    await public_request_service.verify_recaptcha(payload.recaptcha_token)
    created = await public_request_service.create_language_request(
        db,
        requester_name=payload.requester_name,
        requester_email=payload.requester_email,
        name=payload.name,
        code=payload.code,
        description=payload.description,
    )
    return PublicRequestResponse.model_validate(created)


@router.post(
    "/requests/project",
    response_model=PublicRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute;20/hour")
async def request_project_creation(
    request: Request,
    payload: PublicProjectRequestCreate,
    db: AsyncSession = Depends(get_db),
) -> PublicRequestResponse:
    await public_request_service.verify_recaptcha(payload.recaptcha_token)
    created = await public_request_service.create_project_request(
        db,
        requester_name=payload.requester_name,
        requester_email=payload.requester_email,
        name=payload.name,
        language_id=payload.language_id,
        description=payload.description,
        new_language_name=payload.new_language_name,
        new_language_code=payload.new_language_code,
    )
    return PublicRequestResponse.model_validate(created)
