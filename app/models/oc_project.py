from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.project import ProjectBaseResponse


class OCProjectListResponse(ProjectBaseResponse):
    member_count: int = 0
    recording_count: int = 0
    total_duration_seconds: float = 0.0
    storyteller_count: int = 0


class OCProjectStatsResponse(BaseModel):
    """Project totals for the dashboard, including the review-flag counters of ENG-373.

    `review_flag_counts` holds an entry for every `ReviewFlagCode`, including the codes no
    recording carries, which report zero, plus any code a stored row still carries after
    being dropped from the enum. A project with nothing pending therefore returns every
    code at zero and never an empty map, so "nothing pending" is `recordings_with_review_flags
    == 0` rather than an empty-map check. Its values do not sum to that count: a recording
    carrying three flags adds one to each of three codes but only one to the distinct count.

    `review_flag_counts` is keyed by plain strings for the same reason `ReviewFlagResponse`
    types its `code` that way — a fourth flag code must not break clients generated against
    today's schema. Zero-filling raises the stakes on that: a new code now appears in every
    project's response the moment it deploys, rather than once some recording carries it.
    """

    project_id: str
    total_recordings: int
    total_duration_seconds: float
    total_file_size_bytes: int
    total_storytellers: int = 0
    review_flag_counts: dict[str, int]
    recordings_with_review_flags: int = 0


class OCProjectInviteCreate(BaseModel):
    email: EmailStr
    role: str = Field(default="member", max_length=30)


class OCProjectInviteResponse(BaseModel):
    id: str
    project_id: str
    project_name: str | None = None
    email: str
    invited_by: str
    status: str
    role: str
    app_key: str | None = None
    created_at: datetime
    accepted_at: datetime | None

    model_config = {"from_attributes": True}
