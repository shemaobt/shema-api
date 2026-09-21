from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.core.enums import PublicRequestKind, PublicRequestStatus

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
        """Exactly one complete language mode: an existing id, or a new name *and* code.

        Refusing both was only half the rule. Neither, and a half-named new language, used to
        pass here and reach the reviewer, where applying the request had nothing to build a
        project on — the approval then died on an assertion instead of telling anyone the form
        was incomplete. The visitor is the one who can still fix it, so the refusal belongs at
        their end of the wire.
        """
        if self.language_id and (self.new_language_name or self.new_language_code):
            raise ValueError("Provide an existing language or a new one, not both")
        if not self.language_id and not (self.new_language_name and self.new_language_code):
            raise ValueError("Provide an existing language, or the name and the code of a new one")
        return self


class PublicRequestReview(BaseModel):
    status: Literal[PublicRequestStatus.APPROVED, PublicRequestStatus.REJECTED]
    reason: str | None = Field(default=None, max_length=2000)


class PublicRequestResponse(BaseModel):
    id: str
    kind: PublicRequestKind
    status: PublicRequestStatus
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
