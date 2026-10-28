"""The retroverificação file in her fields and her order (`retroExport.ts` at her freeze 18fa7c4).

Field names are hers, so they are camelCase here. A key her file leaves out when the source has
nothing is named in `absent_when_none`; every other null is one she writes.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, model_serializer


class _Hers(BaseModel):
    absent_when_none: ClassVar[tuple[str, ...]] = ()

    @model_serializer(mode="wrap")
    def _leave_out_what_has_no_source(self, handler: Any) -> dict[str, Any]:
        served: dict[str, Any] = handler(self)
        for key in self.absent_when_none:
            if served.get(key) is None:
                served.pop(key, None)
        return served


class RetroApprovalFinding(_Hers):
    absent_when_none = ("frase", "idx", "clipKey", "voiced")

    kind: Literal["missing", "addition", "silence", "unclear", "nuance"]
    frase: int | None = None
    idx: str | None = None
    clipKey: str | None = None
    voiced: Literal["now", "before"] | None = None


class RetroApprovalFrase(_Hers):
    n: int
    idx: str
    clipKey: str
    coversFrom: float | None
    coversTo: float | None


class RetroApprovalTake(_Hers):
    key: str
    takeId: str
    sha256: str
    durationMs: int | None
    bytes: int


class RetroApproval(_Hers):
    absent_when_none = ("nuances", "takes")

    v: int
    at: str
    forced: bool
    conferida: bool
    heardComplete: bool
    lastCheckAt: str | None
    findings: list[RetroApprovalFinding]
    nuances: list[RetroApprovalFinding] | None = None
    frases: list[RetroApprovalFrase]
    takes: list[RetroApprovalTake] | None = None


class RetroFrase(_Hers):
    absent_when_none = ("supersedes",)

    n: int
    idx: str
    clipKey: str
    coversFrom: float | None
    coversTo: float | None
    transcript: str
    pass_number: int = Field(serialization_alias="pass")
    recordedAt: str
    supersedes: str | None = None
    stale: bool


class RetroHistoryEntry(_Hers):
    absent_when_none = ("supersedes",)

    idx: str
    clipKey: str
    coversFrom: float | None
    coversTo: float | None
    transcript: str
    pass_number: int = Field(serialization_alias="pass")
    recordedAt: str
    supersedes: str | None = None
    superseded: bool


class RetroCheckFinding(_Hers):
    absent_when_none = ("frase", "idx", "clipKey", "quote", "story", "voiced")

    kind: Literal["missing", "addition", "silence", "unclear", "nuance"]
    note: str
    frase: int | None = None
    idx: str | None = None
    clipKey: str | None = None
    quote: str | None = None
    story: str | None = None
    voiced: Literal["now", "before"] | None = None


class RetroCheck(_Hers):
    at: str
    findings: list[RetroCheckFinding]
    spoken: str
    outcome: str
    conferida: bool


class RetroSupersededTake(_Hers):
    key: str
    takeId: str
    sha256: str
    durationMs: int | None
    bytes: int
    contentType: str
    recordedAt: str
    filename: str
    url: str


class RetroPrevious(_Hers):
    at: str
    grain: Literal["whole", "scene"]


class RetroExport(_Hers):
    absent_when_none = ("note", "previous")

    releaseId: str
    pericopeId: str
    version: int
    finalized: bool
    note: str | None = None
    approval: RetroApproval | None
    frases: list[RetroFrase]
    history: list[RetroHistoryEntry]
    checks: list[RetroCheck]
    heardByClip: dict[str, float]
    supersededTakes: list[RetroSupersededTake]
    previous: list[RetroPrevious] | None = None
    exportedAt: str
