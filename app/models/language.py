from datetime import datetime

from pydantic import BaseModel, Field


class LanguageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=3)


class LanguageResponse(BaseModel):
    id: str
    name: str
    code: str
    is_active: bool
    created_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
