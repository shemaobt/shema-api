from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.db.models.project_health import PHInterviewStatus, PHLanguage

DOMAIN_KEYS = (
    "local_leadership",
    "capacity_training",
    "church_community",
    "resources_infrastructure",
    "strategic_planning",
    "collaboration",
    "pace_trajectory",
)

OPENING_FIELD_KEYS = (
    "respondent_name",
    "participants_present",
    "language_name",
    "language_code_or_unknown",
    "team_size",
    "team_roles",
)


class MessageOut(BaseModel):
    role: Literal["facilitator", "team"]
    content: str
    timestamp: str


class CoverageState(BaseModel):
    domains_touched: dict[str, int] = Field(default_factory=dict)
    domains_with_evidence: list[str] = Field(default_factory=list)
    suggested_next_domain: str | None = None
    interview_phase: Literal["opening", "exploring", "deepening", "closing"] = "opening"
    turn_count: int = 0
    opening_fields: dict[str, bool] = Field(default_factory=dict)
    missing_opening_fields: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    domain: str
    quote_summary: str
    sentiment: Literal["positive", "neutral", "concern"]
    turn_index: int


class DomainScore(BaseModel):
    domain: str
    score: float
    confidence: float
    rationale: str
    risks: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    evidence_refs: list[int] = Field(default_factory=list)


class InterviewContext(BaseModel):
    respondent_name: str = ""
    participants_present: list[str] = Field(default_factory=list)
    language_name: str = ""
    language_code: str = ""
    team_size: str = ""
    team_roles: list[str] = Field(default_factory=list)


class InterviewQuality(BaseModel):
    coverage_breadth: float
    evidence_depth: float
    confidence_avg: float


class TeamReport(BaseModel):
    interview_context: InterviewContext | None = None
    summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    growth_areas: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    closing: str = ""
    partial_coverage: bool = False
    missing_domains: list[str] = Field(default_factory=list)


class AdminReport(BaseModel):
    overall_sustainability_index: float
    domain_scores: list[DomainScore]
    top_risks: list[str] = Field(default_factory=list)
    evidence_highlights: list[EvidenceItem] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    interview_context: InterviewContext | None = None
    interview_quality: InterviewQuality


class InterviewCreate(BaseModel):
    project_name: str = Field(min_length=1, max_length=200)
    team_name: str = Field(min_length=1, max_length=200)
    language: PHLanguage


class InterviewCreateResponse(BaseModel):
    id: str
    interview_token: str
    expires_at: datetime
    first_message: MessageOut
    coverage: CoverageState


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class InterviewMessageResponse(BaseModel):
    facilitator_message: MessageOut
    coverage: CoverageState


class InterviewDetailResponse(BaseModel):
    id: str
    project_name: str
    team_name: str
    language: PHLanguage
    status: PHInterviewStatus
    messages: list[MessageOut]
    coverage: CoverageState
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class InterviewCompleteResponse(BaseModel):
    report_id: str
    team_report: TeamReport


class InterviewCompleteBlockedResponse(BaseModel):
    error: str
    completion_ready: bool = False
    minimum_team_turns: int
    team_turn_count: int
    missing_opening_fields: list[str]
    missing_domains: list[str]


class InterviewSummary(BaseModel):
    id: str
    project_name: str
    team_name: str
    language: PHLanguage
    status: PHInterviewStatus
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReportSummary(BaseModel):
    id: str
    interview_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminDashboardResponse(BaseModel):
    interviews: list[InterviewSummary]
    reports: list[ReportSummary]


class TeamReportResponse(BaseModel):
    id: str
    interview_id: str
    #: Carried from the interview, not from the model's reading of the transcript. The team
    #: typed these when they began; a report that cannot name the team it is addressed to
    #: reads as a form letter, and no extraction should be able to lose them.
    project_name: str
    team_name: str
    language: PHLanguage
    team_report: TeamReport
    created_at: datetime


class AdminReportResponse(BaseModel):
    id: str
    interview_id: str
    language: PHLanguage
    team_report: TeamReport
    admin_report: AdminReport
    created_at: datetime


class AdminInviteRequest(BaseModel):
    email: EmailStr


class AdminInviteResponse(BaseModel):
    email: EmailStr
    pre_approved_role: str
    access_request_id: str | None = None
    granted: bool


class AgentPromptResponse(BaseModel):
    id: str
    prompt_key: str
    name: str
    description: str
    template: str
    placeholders: list[str]
    version: int
    updated_by: str | None
    created_at: datetime
    updated_at: datetime


class AgentPromptListResponse(BaseModel):
    prompts: list[AgentPromptResponse]


class AgentPromptUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    template: str | None = None
