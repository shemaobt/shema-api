from datetime import datetime

from pydantic import BaseModel, Field, field_validator

ICON_KEYS = (
    "compass",
    "search",
    "clipboard",
    "pen",
    "code",
    "flask",
    "rocket",
    "wrench",
    "users",
    "star",
    "cog",
    "file",
    "mic",
    "book",
    "film",
    "globe",
    "layers",
    "target",
)

COLOR_PATTERN = r"^#[0-9A-Fa-f]{6}$"


class JourneyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)


class JourneyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)


class JourneyResponse(BaseModel):
    id: str
    name: str
    description: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    phase_count: int
    project_count: int

    model_config = {"from_attributes": True}


class PhaseCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(pattern=COLOR_PATTERN)
    icon: str

    @field_validator("icon")
    @classmethod
    def validate_icon(cls, value: str) -> str:
        if value not in ICON_KEYS:
            raise ValueError(f"icon must be one of: {', '.join(ICON_KEYS)}")
        return value


class PhaseCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = Field(default=None, pattern=COLOR_PATTERN)
    icon: str | None = None

    @field_validator("icon")
    @classmethod
    def validate_icon(cls, value: str | None) -> str | None:
        if value is not None and value not in ICON_KEYS:
            raise ValueError(f"icon must be one of: {', '.join(ICON_KEYS)}")
        return value


class PhaseCategoryResponse(BaseModel):
    id: str
    name: str
    color: str
    icon: str
    phase_count: int

    model_config = {"from_attributes": True}


class PhaseStatusLogResponse(BaseModel):
    id: str
    project_id: str
    phase_id: str
    from_status: str
    to_status: str
    note: str | None
    changed_by: str | None
    changed_by_name: str | None
    is_admin_author: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectJourneyAssign(BaseModel):
    journey_id: str | None
