from datetime import datetime
from typing import Literal

from pydantic import BaseModel

UserRole = Literal["member", "manager", "platform_admin"]


class UserListResponse(BaseModel):
    id: str
    email: str
    display_name: str | None
    avatar_url: str | None
    is_active: bool
    is_platform_admin: bool
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    is_active: bool | None = None
    is_platform_admin: bool | None = None
    avatar_url: str | None = None


class UserRoleUpdate(BaseModel):
    role: UserRole
    project_ids: list[str] | None = None


class UserRoleResponse(BaseModel):
    app_key: str
    role_key: str
    granted_at: datetime
