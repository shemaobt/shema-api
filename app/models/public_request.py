from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

LANGUAGE_CODE_PATTERN = r"^[A-Za-z]{3}$"


class PublicLanguageOption(BaseModel):
    id: str
    name: str
    code: str

    model_config = {"from_attributes": True}


class PublicLanguageRequestCreate(BaseModel):
    requester_name: str = Field(min_length=1, max_length=200)
    requester_email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(pattern=LANGUAGE_CODE_PATTERN)
    description: str | None = Field(default=None, max_length=10000)
    recaptcha_token: str | None = None


class PublicProjectRequestCreate(BaseModel):
    requester_name: str = Field(min_length=1, max_length=200)
    requester_email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    language_id: str | None = None
    new_language_name: str | None = Field(default=None, max_length=200)
    new_language_code: str | None = Field(default=None, pattern=LANGUAGE_CODE_PATTERN)
    recaptcha_token: str | None = None

    @model_validator(mode="after")
    def _one_language_mode(self) -> "PublicProjectRequestCreate":
        if self.language_id and (self.new_language_name or self.new_language_code):
            raise ValueError("Provide an existing language or a new one, not both")
        return self


class PublicRequestReview(BaseModel):
    status: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=2000)


class PublicRequestResponse(BaseModel):
    id: str
    kind: str
    status: str
    requester_name: str
    requester_email: str
    name: str
    code: str | None
    description: str | None
    language_id: str | None
    new_language_name: str | None
    new_language_code: str | None
    requested_at: datetime

    model_config = {"from_attributes": True}


class PublicRequestAdminResponse(PublicRequestResponse):
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_reason: str | None
    created_entity_id: str | None
