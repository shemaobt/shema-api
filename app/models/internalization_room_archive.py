"""What a facilitator's Zerar answers: the archive it left, or that nothing was live."""

from __future__ import annotations

from pydantic import BaseModel


class KeptPart(BaseModel):
    #: The part number the tablet sent, null for the passage told whole.
    part: int | None
    take_id: str


class ArchivedSession(BaseModel):
    """One stamped session as it stood when Zerar took it."""

    session_id: str
    language: str
    status: str
    coverage: dict[str, str]
    #: The guide's lines in the conversation, her ``turnCount``.
    turns: int
    #: The parts kept, the newest rehearsal under each number, in reading order.
    kept_takes: list[KeptPart]
    #: The versions of the releases minted on this session, ascending.
    release_versions: list[int]
    created_at: str
    updated_at: str


class ArchiveView(BaseModel):
    id: str
    project_id: str
    pericope: str
    archived_at: str
    archived_by: str
    sessions: list[ArchivedSession]


class ArchiveResponse(BaseModel):
    """200 in both cases: a pericope with nothing live is not a conflict (ADR 0047)."""

    archived: bool
    archive: ArchiveView | None = None
