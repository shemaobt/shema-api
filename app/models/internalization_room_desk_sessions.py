"""The Desk's list of every session the reader may read, across teams (ENG-1192)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.models.internalization_room import MomentView


class DeskSessionState(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    NEEDS_PERSON = "needs_person"


class DeskSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    team_id: str
    team_name: str
    pericope: str
    reference: str | None
    language: str
    state: DeskSessionState
    started_at: datetime
    last_activity_at: datetime
    scene: str | None
    moment: MomentView | None
    ended_at: datetime | None
    attended_at: datetime | None
    attended_by: str | None
    halts_raised: int
    warned_at: datetime | None
    turns: int
    earlier_passages: dict[str, str] | None
    engaged_elements: int | None
    total_elements: int | None
    kept_rehearsals: int
    has_release: bool
    listener_count: int | None


class DeskSessionsPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sessions: list[DeskSession]
    next_cursor: str | None
