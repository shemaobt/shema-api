"""The wire of the text seam's back-translation door, and the model calls every seam reports.

Her back-translation runner speaks these shapes, so the fields here are hers — `sessionId`,
`pericopeId`, `frases`, `outcome` — spelled as she spells them and not in the room's own
snake_case.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Outcome = Literal["pass", "corrected", "fail_safe"]


class ModelCall(BaseModel):
    """One answered model call, in the names the room's own usage line already uses."""

    #: Who asked — `guide`, `validator`, `classifier` — the way her `[llm-usage]` line is
    #: labelled, so a run can add up the Guide and the Validator apart from the rest.
    role: str
    rung: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    #: Filled once the room's usage line carries it; the whole turn's wall clock is `latencyMs`.
    latency_ms: int | None
    #: At list price, as the room's own line prices it; null for a rung the table never priced.
    cost_usd: float | None


class DeclaredClip(BaseModel):
    """One of her draft clips: a key and a length, and no audio anywhere.

    A clip is the **Part** the team would have recorded and listened to. Her scripts declare
    it instead of uploading it, because what the back-translation check reads is the telling,
    never the recording — and a length is all the listening gate needs to be satisfiable.
    """

    key: str = Field(max_length=120)
    durationMs: int = Field(ge=0)


class DeclareBackTranslationSessionRequest(BaseModel):
    pericopeId: str = Field(max_length=120)
    language: str = Field(max_length=40)
    clips: list[DeclaredClip]


class DeclaredPart(BaseModel):
    key: str
    takeId: str


class DeclaredBackTranslationSessionResponse(BaseModel):
    sessionId: str
    #: The take each of her clip keys became, so a reader of the report can tie one to the other.
    parts: list[DeclaredPart]


class TextFrase(BaseModel):
    """One frase told back, in the place a recording and its transcript would have been.

    `supersedes` is her index of the frase this one tells again. The room needs no index: the
    slice names the stretch that stands there, and `current_stretch_at` answers which it is.
    Her number is read only as *this frase is a retelling*, which is what it means.
    """

    clipKey: str = Field(max_length=120)
    #: Seconds into the clip, as her scripts write them; the room addresses in milliseconds.
    coversFrom: float = Field(ge=0)
    coversTo: float = Field(ge=0)
    text: str
    supersedes: int | None = None


class TextRoundRequest(BaseModel):
    sessionId: str = Field(max_length=36)
    frases: list[TextFrase]


class RoundFinding(BaseModel):
    kind: str
    note: str
    #: Her `frase`, which is our **Chunk**: the number the analyst gave. Null when the reply
    #: named no readable position, which is the case her item 1 leaves open.
    frase: int | None
    stretchId: str | None


class TextRoundResponse(BaseModel):
    sessionId: str
    #: Every finding of the reading, with the turn's own **Swap** led by its addition at the
    #: front and the rest in the analyst's order. Her `no_kinds` and `no_finding` sweep this
    #: list, so a finding held back here would read to her judge as one the room never raised.
    findings: list[RoundFinding]
    spoken: str
    outcome: str
    #: Our **Checked**, under the name her scripts expect.
    conferida: bool
    findingsRemaining: int
    #: How often the model left the frase number off a missing finding. Her item 1 leaves it
    #: optional while our output block requires it, and nothing arbitrates until she rules, so
    #: the seam counts instead of guessing.
    missingWithoutFrase: int
    usage: list[ModelCall]
    roundMs: int
