from fastapi import APIRouter, status

from app.api.annotation_studio._deps import AdminUser, Db
from app.models.annotation_studio import LanguageMemberCreate, LanguageMemberResponse
from app.services.annotation_studio import member_service

router = APIRouter()


@router.get(
    "/languages/{language_id}/members",
    response_model=list[LanguageMemberResponse],
)
async def list_members(language_id: str, db: Db, _: AdminUser) -> list[LanguageMemberResponse]:
    rows = await member_service.list_members(db, language_id)
    return [
        LanguageMemberResponse(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            created_at=member.created_at,
        )
        for member, user in rows
    ]


@router.post(
    "/languages/{language_id}/members",
    response_model=LanguageMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    language_id: str, payload: LanguageMemberCreate, db: Db, admin: AdminUser
) -> LanguageMemberResponse:
    member, user = await member_service.add_member(db, language_id, payload.email, admin.id)
    return LanguageMemberResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        created_at=member.created_at,
    )


@router.delete(
    "/languages/{language_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(language_id: str, user_id: str, db: Db, _: AdminUser) -> None:
    await member_service.remove_member(db, language_id, user_id)
