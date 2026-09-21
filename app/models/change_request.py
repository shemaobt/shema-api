from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.db.models.change_request import ChangeRequestKind, ChangeRequestStatus


class ChangeRequestCreate(BaseModel):
    kind: ChangeRequestKind
    name: str | None = Field(default=None, max_length=200)
    code: str | None = Field(default=None, max_length=3)
    description: str | None = Field(default=None, max_length=10000)
    language_id: str | None = None
    new_language_name: str | None = Field(default=None, max_length=200)
    new_language_code: str | None = Field(default=None, max_length=3)


class ChangeRequestReview(BaseModel):
    status: Literal[ChangeRequestStatus.APPROVED, ChangeRequestStatus.REJECTED]
    reason: str | None = Field(default=None, max_length=2000)
    grant_manager_access: bool = False


class ChangeRequestResponse(BaseModel):
    id: str
    kind: ChangeRequestKind
    requester_user_id: str
    requester_display_name: str | None
    requester_email: str
    status: ChangeRequestStatus
    name: str | None
    code: str | None
    description: str | None
    language_id: str | None
    new_language_name: str | None
    new_language_code: str | None
    grant_manager_access: bool
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_reason: str | None
    created_entity_id: str | None
    requested_at: datetime
