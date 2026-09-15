from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.phase import PhaseStatus


class PhaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)


class PhaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)


class PhaseResponse(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    project_ids: list[str] | None = None

    model_config = {"from_attributes": True}


class ProjectPhaseResponse(BaseModel):
    id: str
    phase_id: str
    phase_name: str
    phase_description: str | None
    status: PhaseStatus

    model_config = {"from_attributes": True}


class ProjectPhaseStatusUpdate(BaseModel):
    status: PhaseStatus


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
