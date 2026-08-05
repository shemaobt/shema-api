from datetime import datetime

from pydantic import BaseModel, Field


class PhaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    journey_id: str
    category_id: str | None = None


class PhaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    category_id: str | None = None
    icon_url: str | None = Field(default=None, max_length=500)


class PhaseResponse(BaseModel):
    id: str
    name: str
    description: str | None
    journey_id: str | None
    category_id: str | None
    sort_order: int
    icon_url: str | None
    created_at: datetime
    updated_at: datetime
    project_ids: list[str] | None = None

    model_config = {"from_attributes": True}


class PhaseReorderRequest(BaseModel):
    journey_id: str
    phase_ids: list[str]


class ProjectPhaseResponse(BaseModel):
    id: str
    phase_id: str
    phase_name: str
    phase_description: str | None
    status: str

    model_config = {"from_attributes": True}


class ProjectPhaseStatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=20)
    note: str | None = Field(default=None, max_length=10000)


class DependencyCreate(BaseModel):
    depends_on_id: str


class PhaseDependencyResponse(BaseModel):
    id: str
    phase_id: str
    depends_on_id: str

    model_config = {"from_attributes": True}


class PhasesWithDepsResponse(BaseModel):
    phases: list[PhaseResponse]
    dependencies: dict[str, list[str]]


class ProjectPhasesWithDepsResponse(BaseModel):
    phases: list[ProjectPhaseResponse]
    dependencies: dict[str, list[str]]


class AttachPhaseRequest(BaseModel):
    phase_id: str
