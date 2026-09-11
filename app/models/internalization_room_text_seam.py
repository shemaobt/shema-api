"""The wire of the text seam, in the names her golden runner already speaks.

The runner points at her Next.js app or at this room by changing one base URL and nothing
else, so the request and response fields here are hers — `sessionId`, `pericopeId`,
`guideText`, `outcome` — spelled as she spells them and not in the room's own snake_case.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class OpenTextSessionRequest(BaseModel):
    pericopeId: str = Field(max_length=120)
    #: Her scripts name the language the way a person would — `Brazilian Portuguese` — and
    #: the room speaks in codes; either form is accepted.
    language: str = Field(max_length=40)


class TextSessionResponse(BaseModel):
    sessionId: str
    pericopeId: str
    language: str


class TextTurnRequest(BaseModel):
    sessionId: str = Field(max_length=36)
    #: What the team said, in the place the transcriber's words would have gone.
    text: str | None = None
    #: The session has just opened and the Guide speaks first. Only ever on a fresh session.
    kickoff: bool = False


class TextTurnResponse(BaseModel):
    sessionId: str
    transcript: str
    guideText: str
    #: What the judge is defined against: the Guide's own words (`pass`), the Validator's
    #: mended version of them (`corrected`), or a pre-approved line (`fail_safe`).
    outcome: str
