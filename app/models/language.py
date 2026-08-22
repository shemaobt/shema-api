from datetime import datetime

from pydantic import BaseModel, Field


class LanguageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=3)


class LanguageResponse(BaseModel):
    id: str
    name: str
    code: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LanguageProjectRef(BaseModel):
    id: str
    name: str


class LanguageStatsResponse(BaseModel):
    language_id: str
    project_count: int
    projects: list[LanguageProjectRef]
