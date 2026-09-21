from app.db.models.auth import User
from app.models.user import UserListResponse, UserRole


def build_user_list_response(user: User, *, is_manager: bool) -> UserListResponse:
    role: UserRole = (
        "platform_admin" if user.is_platform_admin else "manager" if is_manager else "member"
    )
    return UserListResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_active=user.is_active,
        is_platform_admin=user.is_platform_admin,
        role=role,
        created_at=user.created_at,
    )
