from __future__ import annotations

import enum
import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.exceptions import UpstreamServiceError
from app.db.models.internalization_room import IRSegment
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.languages import FLOOR, LANGUAGE_NAMES
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


class VoicedVerdict(BaseModel):
    """The verdict as the team actually received it, kept so a repeat press can serve it.

    The findings beside it are what the room decided; this is what it said, which does not
    follow from them — the wording came from the Speaker and the address from the synthesiser.
    Without it a second press has to voice the verdict again in order to answer at all, which
    is the cost the guard above exists to avoid.
    """

    clip_key: str = ""
    fixed_line: str = ""
    used_fail_safe: bool = False


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
    #: Which rehearsal recordings the report above is about: the ones the telling-back stood
    #: on when the report was stored, stamped by the server. The two fields beside it are
    #: numbers with no subject — they say a clip was played through without saying which clip,
    #: so they went on reading as proof after the team threw that recording away and started
    #: the telling-back over on a new one.
    #:
    #: The subject is taken from the stretches rather than from the takes table because a
    #: stretch names the recording it is a slice of, checked when it was captured, and that
    #: answer does not move. Which take is "the newest" does: `created_at` is stamped when the
    #: upload lands, and the tablet's outbox drains whenever the link comes back, so a rehearsal
    #: the team abandoned can be written down after the one that replaced it.
    #:
    #: The server stamps it because the tablet cannot be asked to. Naming the recording in the
    #: `finish` payload would mean every app already in the field stops being able to release.
    played_take_ids: list[str] = Field(default_factory=list)
    #: How many stretches the team has told back a second time. The retell is the one cycle
    #: the team can repeat at will, so the budget lives here — a counter the app cannot
    #: reach, which is what keeps a loop from being a loop.
    retells: int = 0
    #: How many times the first-round gate has already turned the team back. It is what
    #: rotates the waiting line, and it cannot be read off the conversation: the gate answers
    #: before the turn loop, so no exchange is appended and a rotation keyed on the messages
    #: stands still — the room would repeat one sentence word for word every press.
    waited: int = 0
    #: Which stretches the analyst has already read, by address. `terminei` is not idempotent
    #: on its own — every press re-ran the analyst over a growing transcript — so a second
    #: press with nothing new told back reuses the verdict instead of paying for it again.
    #:
    #: This list alone answered that only for the analyst, while the validator, the spoken
    #: synthesis and the transcript write went on running every press: two model calls nobody
    #: asked for, and a conversation that recorded the room as having spoken twice. It is the
    #: signal for all four now, and `verdict` below is what a guarded press serves.
    #:
    #: The addresses and not a count. A count answered "how many stretches" and a replaced
    #: stretch leaves that number exactly where it was, so a re-recorded telling-back would
    #: have been served the verdict of the one it replaced. `None` is never read at all, which
    #: an empty list is not.
    analysed_segment_ids: list[str] | None = None
    #: What the room said when it last reached a verdict, so a press that decides nothing new
    #: can hand back the same answer without voicing it again. `None` until a verdict has been
    #: spoken *and* stored, which is what separates "already judged" from a press that reached
    #: the analyst and then failed before the team heard anything — that one saves nothing at
    #: all, and the press after it does the whole turn.
    verdict: VoicedVerdict | None = None

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
    at either edge or between stretches. This is the arithmetic only: an absent report is
    not a short one, so it is not this function's to judge and comes back True. Whether a
    report exists at all, and whether it is about the recording still in play, is
    `playback_confirms_rehearsal`, which is what the release gate asks.

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


def playback_confirms_rehearsal(state: BackTranslationState, rehearsal_take_ids: list[str]) -> bool:
    """Whether the team has evidence of hearing the rehearsal they told back about, whole.

    Three things have to hold together, and each one alone was a way through. The report has
    to exist: no report is silence, and silence used to read as consent because empty ranges
    over an empty duration satisfied the coverage arithmetic — which is what a `finish` with
    no body produces, and what the shipped app sends whenever the clip did not run to its end.
    It has to be about the recordings the telling-back is still standing on: once the team
    starts over on a clip they recorded again, a report made against the old one describes
    audio nobody will hear. And it has to reach the end of that clip, which is the check that
    was already here.

    Both numbers are required rather than either. A duration with no ranges is a report that
    nothing was played, and ranges with no duration cannot be checked against anything —
    taking either as proof reopens the same hole through a smaller door.
    """
    if not state.played_take_ids or sorted(state.played_take_ids) != sorted(rehearsal_take_ids):
        return False
    if not state.played_ranges or not state.clip_duration_ms:
        return False
    return played_ranges_cover_clip(state.played_ranges, state.clip_duration_ms)


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


def _refused(condition: str, raw: str, session: str) -> None:
    """Every refusal leaves the reply behind it, whole, with the condition that refused.

    Five of the seven exits below used to return None in silence. A reply the model did
    produce was then indistinguishable from one it never did, and the night of 2026-09-01
    was spent unable to say what the analyst had answered. The reply is logged whole
    rather than cut at a few hundred characters: it is bounded by the call's output cap,
    and a truncated reply is exactly what could not be diagnosed. The session is named so
    the line can be tied to the request that got the 502, across replicas and teams.
    """
    logger.warning("BT analyst reply refused (%s) for session %s: %s", condition, session, raw)


def _session_of(segments: list[IRSegment]) -> str:
    return segments[0].session_id if segments else "?"


def _parse_analysis(raw: str, segments: list[IRSegment]) -> BtAnalysis | None:
    """The analyst's reply read atomically, or None when it cannot be trusted at all.

    None and an empty findings list must stay apart all the way up: empty is "read it,
    nothing to raise", which closes the necklace, and None is "never read it", which must
    not. The reading is atomic on purpose — the old parser skipped a malformed entry with
    a warning, and a reply whose only finding was malformed then counted as a clean
    telling-back and blessed the passage. A "silence" kind is folded into addition: a
    filled silence is something told that the passage does not tell.

    A reply without ``evidence_sufficient`` is from a prompt version that predates the
    field; it is read as sufficient, exactly what that prompt's replies always meant. When
    the field is present it must agree with the findings one way: insufficient needs a
    finding that names the limit, or nothing concrete reaches the Voice.

    The other way it is allowed to disagree, and the disagreement is resolved rather than
    refused. **A sufficient flag beside an ``insufficient_evidence`` finding is read as
    insufficient, and every finding is kept.** The prompt defines that finding as the
    statement that a real part of the scope could not be compared, naming the stretch;
    the flag is that same statement summarised over the scope, with no information of its
    own. When they disagree the flag is the side without evidence. The alternatives are
    both worse: refusing the reply threw away a good ``meaning_change`` together with the
    contradiction (ENG-719, the session that stopped a team three times), and letting the
    flag win would have marked as checked a passage the analyst itself said stops at
    verse 8. Whoever reads this as a contradiction to be refused: it was, and that is
    what it cost. The analyst did break the contract its prompt writes, so the case is
    logged with the reply — silence about a model's drift is how the next one goes
    unnoticed too.
    """
    session = _session_of(segments)
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError:
        _refused("not JSON", raw, session)
        return None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("findings"), list):
        _refused("findings is not a list", raw, session)
        return None
    sufficient_raw = parsed.get("evidence_sufficient", True)
    if not isinstance(sufficient_raw, bool):
        _refused("evidence_sufficient is not a boolean", raw, session)
        return None

    findings: list[Finding] = []
    for entry in parsed["findings"]:
        if not isinstance(entry, dict):
            _refused("an entry in findings is not an object", raw, session)
            return None
        kind_raw = str(entry.get("kind", ""))
        if kind_raw == "silence":
            kind_raw = FindingKind.ADDITION.value
        note = str(entry.get("note", "")).strip()
        if not note:
            _refused("a finding has an empty note", raw, session)
            return None
        try:
            kind = FindingKind(kind_raw)
        except ValueError:
            _refused(f"unknown finding kind {kind_raw!r}", raw, session)
            return None
        findings.append(
            Finding(
                kind=kind,
                note=note[:1000],
                segment_id=_segment_pointed_at(entry.get("chunk"), segments),
            )
        )

    if not sufficient_raw and not any(f.kind in EVIDENCE_LIMIT_KINDS for f in findings):
        _refused("evidence_sufficient is false and no finding names the limit", raw, session)
        return None
    if sufficient_raw and any(f.kind is FindingKind.INSUFFICIENT_EVIDENCE for f in findings):
        logger.warning(
            "BT analyst said evidence_sufficient is true beside an insufficient_evidence "
            "finding for session %s; the finding wins and the reply is read as "
            "insufficient: %s",
            session,
            raw,
        )
        sufficient_raw = False
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
    session_language: str = LANGUAGE_NAMES[FLOOR],
    settings: Settings | None = None,
) -> BtAnalysis | None:
    """Compare the bridge-language telling-back against the map. Never voiced.

    The system never hears the mother-tongue recording; it only ever sees what the team told
    back. The analyst under-reports by design — it never invents a finding when unsure.

    But under-reporting is not the same as not reporting. Returning a clean analysis when
    the call itself failed made an outage indistinguishable from a clean telling-back, and
    the room then told the team their work was checked and closed the passage for good.
    Only a real, sufficient, findingless analysis may mean "ran, and found nothing".

    The two ways of not having an analysis are kept apart here, because the route answers
    them differently. A provider that failed raises ``UpstreamServiceError`` from this
    boundary, with the cause attached and the stack trace logged. A provider that answered
    something the parser refused returns None — the parser has already logged the reply
    and why — and that is not an outage, whatever the old single None used to say.
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
    except Exception as failure:
        logger.exception("BT analysis failed for %s", pericope_num)
        raise UpstreamServiceError(
            "a análise do contado de volta não pôde ser feita agora"
        ) from failure
    return _parse_analysis(raw, segments)


def findings_block(finding: Finding | None) -> str:
    """Exactly one finding reaches the Speaker; the rest wait for the next round."""
    if finding is None:
        return "(nenhum achado — o contado de volta está completo)"
    return f"- {finding.kind}: {finding.note}"


CLOSING_ON_SCREEN = """- End by handing the choice to the screen, not by asking for a spoken \
answer. This stretch is on screen with its two voices side by side: theirs, in their own \
language, and the telling in {session_language}. Ask the boundary question above, then in one \
short sentence tell them they can listen to both and tap the microphone of the voice that has \
to speak again. Do not ask them to say the answer out loud, and do not offer any other next \
step — the screen offers exactly those two, and naming a third promises something they cannot \
do. Remaining findings wait for the next round. Never a checklist, never a speech."""

CLOSING_PLAIN = """- End with exactly one answerable question or invitation. Remaining \
findings wait for the next round. Never a checklist, never a speech."""
#: Word for word what this prompt closed with before the screen existed. A turn with no finding
#: at all affirms and names the badge; both other closings explain themselves in terms of *this
#: finding*, and there is none — `findings_block` is saying so in the same prompt.

CLOSING_SPOKEN = """- End with exactly one answerable question or invitation, and let them \
answer in words. This finding does not land on one stretch, so there is no stretch on screen \
and no two voices to choose between — the next conversational turn will respond to what they \
say. Remaining findings wait for the next round. Never a checklist, never a speech."""


def closing_block(finding: Finding | None) -> str:
    """How the Speaker is told to end this turn: handing to the screen, or asking out loud.

    Chosen here rather than by the Speaker reading a branch, because the finding carries the
    deciding fact and the prompt does not: `findings_block` sends kind and note, never the
    address. A prompt that branched would be asking a model not to promise a choice the screen
    will not offer; injecting one closing means the wrong instruction is never in front of it.

    The deciding fact is not whether the finding has an address — it is whether a boundary
    question was asked. `unclear` names a stretch and still asks only for that piece again, and
    the screen exists to answer *"is it in your recording, or did it come in with the telling?"*.
    Where that question is not put, there is no choice to hand over.

    Returned with `{session_language}` still in it, for whoever fills the template to
    substitute from the same value it gives `{{SESSION_LANGUAGE}}`. Naming the language here
    would mean two defaults that agree by luck, and the day a caller passes a language to the
    turn the closing would go on saying Portuguese. It is not left as a `{{...}}` placeholder
    because `render` fills in one pass: one arriving inside an injected value is never seen
    again and reaches the model as literal braces.
    """
    if finding is None:
        return CLOSING_PLAIN
    asks_where_the_error_lives = (
        finding.segment_id is not None and finding.kind not in EVIDENCE_LIMIT_KINDS
    )
    return CLOSING_ON_SCREEN if asks_where_the_error_lives else CLOSING_SPOKEN
