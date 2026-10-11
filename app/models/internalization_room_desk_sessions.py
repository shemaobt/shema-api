"""The Desk's list of every session the reader may read, across teams (ENG-1192)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


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
    last_activity_at: datetime
    ended_at: datetime | None
    turns: int
    engaged_elements: int
    total_elements: int
    kept_rehearsals: int
    has_release: bool
    listener_count: int | None


class DeskSessionsPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sessions: list[DeskSession]
    next_cursor: str | None
