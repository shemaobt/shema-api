from __future__ import annotations

import enum
import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.db.models.internalization_room import IRSegment
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.llm import call_agent
from app.services.internalization_room.render import render

logger = logging.getLogger(__name__)


class FindingKind(enum.StrEnum):
    MISSING = "missing"
    ADDITION = "addition"
    MEANING_CHANGE = "meaning_change"
    WRONG_RELATION = "wrong_relation"
    REORDERED_EVENT = "reordered_event"
    PRESERVATION_VIOLATION = "preservation_violation"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNCLEAR = "unclear"


EVIDENCE_LIMIT_KINDS = frozenset({FindingKind.INSUFFICIENT_EVIDENCE, FindingKind.UNCLEAR})


class Finding(BaseModel):
    kind: FindingKind
    note: str
    #: Which stretch the finding lands on, by the segment's own address. The team fixes one
    #: stretch of the recording, not the whole passage, so a finding that cannot name its
    #: stretch cannot be acted on. `None` when the analyst could not attribute it — the room
    #: then falls back to the whole clip, which is what it always did.
    #:
    #: It was the stretch's position in a list, which named nothing the moment the list
    #: changed. The analyst still answers with a number, because asking a model to echo an
    #: identifier back is trading a reliable field for one it can invent; the number is read
    #: as a position in the list that call was given and resolved to an address here, where
    #: it is already being validated.
    segment_id: str | None = None


class BtAnalysis(BaseModel):
    """One completed analyst pass.

    ``evidence_sufficient`` is the difference between "no difference appeared" and "there
    was not enough telling-back to look for one". Weak evidence must never read as a
    clean check: when it is False, at least one finding names the limit, so the Voice has
    something concrete to resolve or send to Refine.
    """

    evidence_sufficient: bool = True
    findings: list[Finding] = Field(default_factory=list)


class SupersededAttempt(BaseModel):
    """A telling-back the team replaced by re-recording.

    Its findings do not disappear with the clip: they are the history the Refine artifact
    carries, clearly marked as superseded — the team's open questions survive their own
    retake. The stretches themselves are no longer copied in here; they are rows that stay
    exactly where they are, marked as no longer counting, and `retired_segments` reads them.
    """

    findings: list[Finding] = Field(default_factory=list)
    evidence_sufficient: bool = True
    played_ranges: list[list[int]] = Field(default_factory=list)
    clip_duration_ms: int | None = None


class BackTranslationState(BaseModel):
    """What a telling-back knows that is about the session rather than about one stretch.

    The stretches left: they are rows in `ir_segments` now, with addresses of their own. What
    stays is read and rewritten whole once per analysis, which is the same argument
    `ir_sessions` makes for the transcript and the coverage tracker.
    """

    scope: str = ""
    findings: list[Finding] = Field(default_factory=list)
    evidence_sufficient: bool = True
    checked: bool = False
    superseded: list[SupersededAttempt] = Field(default_factory=list)
    played_ranges: list[list[int]] = Field(default_factory=list)
    clip_duration_ms: int | None = None
    #: How many stretches the team has told back a second time. The retell is the one cycle
    #: the team can repeat at will, so the budget lives here — a counter the app cannot
    #: reach, which is what keeps a loop from being a loop.
    retells: int = 0
    #: Which stretches the analyst has already read, by address. `terminei` is not idempotent
    #: on its own — every press re-ran the analyst over a growing transcript — so a second
    #: press with nothing new told back reuses the verdict instead of paying for it again.
    #:
    #: The addresses and not a count. A count answered "how many stretches" and a replaced
    #: stretch leaves that number exactly where it was, so a re-recorded telling-back would
    #: have been served the verdict of the one it replaced. `None` is never read at all, which
    #: an empty list is not.
    analysed_segment_ids: list[str] | None = None

    @property
    def current_finding(self) -> Finding | None:
        """The one finding the Speaker is allowed to voice this turn."""
        return self.findings[0] if self.findings else None

    def already_analysed(self, segments: list[IRSegment]) -> bool:
        return self.analysed_segment_ids is not None and self.analysed_segment_ids == [
            segment.id for segment in segments
        ]

    @property
    def never_analysed(self) -> bool:
        """The analyst has not read this telling-back at all.

        Distinct from `not already_analysed`, which is also true when more was told back
        after the last pass. Never read is the state whose defaults — no findings, evidence
        sufficient — are indistinguishable from a clean check.
        """
        return self.analysed_segment_ids is None


PLAYBACK_TOLERANCE_MS = 750


def played_ranges_cover_clip(played_ranges: list[list[int]], clip_duration_ms: int | None) -> bool:
    """Whether the reported playback reached the whole clip, within tolerance.

    A telling-back is a check of what was actually heard, not of what the team remembers,
    so "checked" over a half-listened clip would be a claim about audio nobody played.
    Reported ranges are merged and must cover [0, duration] with at most 750 ms of slack
    at either edge or between stretches. No report at all is a legacy client and passes —
    honesty about what we know, not a new wall for old tablets.

    The merged reach has to *land on* the clip's end, not merely reach it: a report that
    runs past the end by more than the same slack cannot be a report about this clip at
    all. That is the signature of ranges belonging to a different audio — typically the
    previous, longer clip, left standing when a piece was replaced under it — and taking
    them as proof would bless as heard a clip nobody played. The slack is the same on
    both sides because it is the same rounding on both sides.
    """
    if not played_ranges or not clip_duration_ms:
        return True
    spans = sorted((max(0, int(start)), int(end)) for start, end in played_ranges if end > start)
    if not spans:
        return False
    cursor = 0
    for start, end in spans:
        if start > cursor + PLAYBACK_TOLERANCE_MS:
            return False
        cursor = max(cursor, end)
    return abs(cursor - clip_duration_ms) <= PLAYBACK_TOLERANCE_MS


def segments_block(segments: list[IRSegment]) -> str:
    """The stretches as the analyst reads them: numbered, in the order the team told them.

    Numbered from one over the list it is given, so the number is a position in *this* call
    and never an identifier the analyst has to keep. `_segment_pointed_at` reads it back the
    same way.
    """
    if not segments:
        return "(a equipe ainda não contou nada de volta)"
    return "\n".join(
        f"{position}. {segment.transcript}" for position, segment in enumerate(segments, start=1)
    )


def _parse_analysis(raw: str, segments: list[IRSegment]) -> BtAnalysis | None:
    """The analyst's reply read atomically, or None when it cannot be trusted at all.

    None and an empty findings list must stay apart all the way up: empty is "read it,
    nothing to raise", which closes the necklace, and None is "never read it", which must
    not. The reading is atomic on purpose — the old parser skipped a malformed entry with
    a warning, and a reply whose only finding was malformed then counted as a clean
    telling-back and blessed the passage. A "silence" kind is folded into addition: a
    filled silence is something told that the passage does not tell.

    A reply without ``evidence_sufficient`` is a legacy prompt still stored in
    ``ir_prompts``; it is read as sufficient, exactly what that prompt's replies always
    meant. When the field is present, it must agree with the findings: insufficient needs
    a finding that names the limit, and sufficient may not carry insufficient_evidence.
    """
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("BT analyst returned unparseable JSON: %s", raw[:300])
        return None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("findings"), list):
        return None
    sufficient_raw = parsed.get("evidence_sufficient", True)
    if not isinstance(sufficient_raw, bool):
        return None

    findings: list[Finding] = []
    for entry in parsed["findings"]:
        if not isinstance(entry, dict):
            return None
        kind_raw = str(entry.get("kind", ""))
        if kind_raw == "silence":
            kind_raw = FindingKind.ADDITION.value
        note = str(entry.get("note", "")).strip()
        if not note:
            return None
        try:
            kind = FindingKind(kind_raw)
        except ValueError:
            logger.warning("BT analyst returned an unknown finding kind: %s", entry)
            return None
        findings.append(
            Finding(
                kind=kind,
                note=note[:1000],
                segment_id=_segment_pointed_at(entry.get("chunk"), segments),
            )
        )

    if not sufficient_raw and not any(f.kind in EVIDENCE_LIMIT_KINDS for f in findings):
        return None
    if sufficient_raw and any(f.kind is FindingKind.INSUFFICIENT_EVIDENCE for f in findings):
        return None
    return BtAnalysis(evidence_sufficient=sufficient_raw, findings=findings)


def _segment_pointed_at(raw: Any, segments: list[IRSegment]) -> str | None:
    """Which stretch the finding lands on, by address, or None when it names none.

    The analyst answers with the position it was given, and the position is turned into an
    address here — the one place that already decides whether the pointer can be trusted. A
    finding the team cannot locate sends them back to the whole recording, so a pointer that
    is not a number, or names a stretch that is not in this reading, degrades to that rather
    than to a stretch that does not exist.
    """
    if isinstance(raw, bool) or not isinstance(raw, int | str):
        return None
    try:
        position = int(raw)
    except ValueError:
        return None
    if position < 1 or position > len(segments):
        return None
    return segments[position - 1].id


async def analyse_telling_back(
    *,
    segments: list[IRSegment],
    scope: str,
    pericope_num: str,
    analyst_prompt: str,
    session_language: str = "Portuguese",
    settings: Settings | None = None,
) -> BtAnalysis | None:
    """Compare the bridge-language telling-back against the map. Never voiced.

    The system never hears the mother-tongue recording; it only ever sees what the team told
    back. The analyst under-reports by design — it never invents a finding when unsure.

    But under-reporting is not the same as not reporting. Returning a clean analysis when
    the call itself failed made an outage indistinguishable from a clean telling-back, and
    the room then told the team their work was checked and closed the passage for good.
    None says "never ran"; only a real, sufficient, findingless analysis may mean "ran,
    and found nothing".
    """
    cfg = settings or get_settings()
    system = render(
        analyst_prompt,
        SESSION_LANGUAGE=session_language,
        SCOPE=scope,
        MEANING_MAP=load_map(pericope_num).body,
        SEGMENTS=segments_block(segments),
    )
    try:
        raw = await call_agent(
            system_prompt=system,
            user_content="Compare o contado de volta com o mapa.",
            temperature=0.0,
            max_output_tokens=2000,
            settings=cfg,
        )
    except Exception:
        logger.exception("BT analysis failed for %s", pericope_num)
        return None
    return _parse_analysis(raw, segments)


def findings_block(finding: Finding | None) -> str:
    """Exactly one finding reaches the Speaker; the rest wait for the next round."""
    if finding is None:
        return "(nenhum achado — o contado de volta está completo)"
    return f"- {finding.kind}: {finding.note}"
