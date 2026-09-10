from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    language_id: str
    latitude: float | None = None
    longitude: float | None = None
    location_display_name: str | None = Field(default=None, max_length=500)


class ProjectMemberPreview(BaseModel):
    user_id: str
    display_name: str | None
    avatar_url: str | None


class ProjectBaseResponse(BaseModel):
    id: str
    name: str
    description: str | None
    language_id: str
    latitude: float | None
    longitude: float | None
    location_display_name: str | None
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectResponse(ProjectBaseResponse):
    team_size: int = 0
    phases_completed: int = 0
    phases_total: int = 0
    members_preview: list[ProjectMemberPreview] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    language_id: str | None = None
    image_url: str | None = Field(default=None, max_length=500)


class ProjectLocationUpdate(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    location_display_name: str | None = Field(default=None, max_length=500)


class ProjectGrantUserAccess(BaseModel):
    user_id: str
    role: str = Field(default="member", max_length=30)


class ProjectUserAccessRoleUpdate(BaseModel):
    role: Literal["member", "manager"]


class ProjectGrantOrganizationAccess(BaseModel):
    organization_id: str


class ProjectUserAccessResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    role: str = "member"
    granted_at: datetime

    model_config = {"from_attributes": True}


class ProjectOrganizationAccessResponse(BaseModel):
    id: str
    project_id: str
    organization_id: str
    granted_at: datetime

    model_config = {"from_attributes": True}


class ProjectUserAccessDetailResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    email: str
    display_name: str | None
    avatar_url: str | None = None
    role: str = "member"
    granted_at: datetime


class ProjectOrganizationAccessDetailResponse(BaseModel):
    id: str
    project_id: str
    organization_id: str
    name: str
    slug: str
    granted_at: datetime
