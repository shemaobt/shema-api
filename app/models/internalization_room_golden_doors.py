"""The wire of the Golden doors, in her runner's own names and meaning.

Her runner (`src/golden/httpDriver.ts`) speaks these shapes to any backend that would be
judged, so the fields here are hers, spelled as she spells them and not in the room's own
snake_case. A key she adds later is ignored, never refused.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, model_serializer

from app.core.room_enums import EarlierPassageStatus
from app.models.internalization_room_text_seam import ModelCall, Outcome

RoomNote = Literal["session_start", "mother_tongue", "interrupted"]


class GoldenSessionRequest(BaseModel):
    """Her `HttpSessionRequest`. A key she adds later is ignored, never refused."""

    pericopeId: str = Field(max_length=120)
    #: Her language name, `Brazilian Portuguese`, or one of the room's codes.
    language: str = Field(max_length=40)
    #: This team's status on each earlier passage of the book, by pericope id.
    earlierPassages: dict[str, EarlierPassageStatus] | None = None


class GoldenSessionResponse(BaseModel):
    sessionId: str


class GoldenTurnRequest(BaseModel):
    """Her `HttpTurnRequest`: the team's words, or a room note in their place."""

    sessionId: str = Field(max_length=36)
    teamText: str | None = None
    roomNote: RoomNote | None = None
    #: How long the team spoke on a `mother_tongue` note.
    seconds: float | None = Field(default=None, ge=0)
    #: Her app's text for the room note; the room renders its own.
    noteText: str | None = None
    #: The team cut the Guide's previous reply short.
    interrupted: bool = False
    #: The full carried list of scene ids whose scene rehearsal has reached the Guide;
    #: `[]` is the fact that none has, and absence is no fact at all.
    sceneRehearsals: list[str] | None = None


class GoldenRehearsalRequest(BaseModel):
    sessionId: str = Field(max_length=36)
    sceneId: str | None = Field(default=None, max_length=16)
    pieces: list[str]


class GoldenRehearsalResponse(BaseModel):
    rehearsalId: str


class GoldenRehearsalSendRequest(BaseModel):
    sessionId: str = Field(max_length=36)
    rehearsalId: str = Field(max_length=36)
    turnId: str = Field(max_length=64)
    closes: uuid.UUID | None = None


class GoldenTurnResponse(BaseModel):
    """Her `HttpTurnResponse`, and the turn's model calls beside it, which she ignores."""

    guideText: str
    outcome: Outcome
    #: What reached the Guide as the team's side of the turn.
    transcript: str
    #: The session is stored as done once this turn has settled its beads.
    complete: bool
    latencyMs: int
    usage: list[ModelCall]
    acceptedIds: list[str] = Field(
        default_factory=list,
        description=(
            "The entries whose accepted readings the Guide was handed, absent when it was "
            "handed none. They come from the rehearsal send: on the turn door the list is "
            "empty today, because a typed turn is never a checking turn."
        ),
    )

    acceptedSendBacks: int = Field(
        default=0,
        description=(
            "How many times the Validator sent the Guide's draft back on a turn that was handed "
            "accepted readings, absent when none. It rides beside `acceptedIds` and is counted "
            "from the same attempts the server's `[accepted-sendback]` warning reports."
        ),
    )

    @model_serializer(mode="wrap")
    def _no_readings_handed_is_absent(self, handler: Any) -> dict[str, Any]:
        served: dict[str, Any] = handler(self)
        if not self.acceptedIds:
            served.pop("acceptedIds", None)
        if not self.acceptedSendBacks:
            served.pop("acceptedSendBacks", None)
        return served
