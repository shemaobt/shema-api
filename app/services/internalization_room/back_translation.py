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
from app.services.internalization_room.fail_safe import FailSafe, first
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
    #: Whether a stretch-by-stretch verification has run since the last whole reading. It is
    #: what the closing gate turns on: a verification answers the finding it was shown and
    #: nothing else, so a list emptied by verifications alone has never been measured against
    #: the set. Two things live only in the set — a correction can answer, by accident, a
    #: finding raised on another stretch, and whether the telling-back is too thin to judge at
    #: all — and `checked` strikes the passage off the wheel for good, with no undo.
    #:
    #: A first reading never turns it on, which is what keeps a team that got it right the
    #: first time paying for one reading and not two.
    verified_since_whole_reading: bool = False
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
    the field is present, it must agree with the findings: insufficient needs a finding
    that names the limit, and sufficient may not carry insufficient_evidence.
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
    session_language: str = LANGUAGE_NAMES[FLOOR],
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


class CorrectionCheck(BaseModel):
    """One verification of one corrected stretch.

    ``resolved`` and ``findings`` are independent on purpose: a correction can answer the
    finding it was asked about and still drop an element only that stretch carried, and it can
    leave the finding standing while breaking nothing. Collapsing them into one verdict would
    make the room unable to tell the team which of the two happened.
    """

    resolved: bool
    findings: list[Finding] = Field(default_factory=list)


#: What the verification may report. Deliberately short of the analyst's list: `missing` here
#: means *this stretch said it before and does not now*, never the analyst's global sense, and
#: the kinds defined over the whole telling-back — `insufficient_evidence`, `reordered_event`,
#: `wrong_relation` — cannot be judged from one stretch at all.
CORRECTION_KINDS = frozenset(
    {
        FindingKind.MISSING,
        FindingKind.ADDITION,
        FindingKind.MEANING_CHANGE,
        FindingKind.PRESERVATION_VIOLATION,
        FindingKind.UNCLEAR,
    }
)


def _parse_correction(raw: str, segment_id: str) -> CorrectionCheck | None:
    """The verification's reply, or None when it cannot be trusted at all.

    None is never "the correction was fine": a verification that did not happen must not be
    readable as one that passed, because a finding dropped on an unparseable reply is a finding
    the team is never asked about again. Read atomically for the same reason `_parse_analysis`
    is — one malformed entry among good ones would otherwise silently shrink the report.

    Every finding is stamped with the corrected stretch's own address: the verification looked
    at exactly one stretch, so there is nowhere else its findings could land, and a finding the
    team cannot locate sends them back to the whole recording for no reason.
    """
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("BT correction returned unparseable JSON: %s", raw[:300])
        return None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("resolved"), bool):
        return None
    raw_findings = parsed.get("findings", [])
    if not isinstance(raw_findings, list):
        return None

    findings: list[Finding] = []
    for entry in raw_findings:
        if not isinstance(entry, dict):
            return None
        note = str(entry.get("note", "")).strip()
        if not note:
            return None
        try:
            kind = FindingKind(str(entry.get("kind", "")))
        except ValueError:
            logger.warning("BT correction returned an unknown finding kind: %s", entry)
            return None
        if kind not in CORRECTION_KINDS:
            logger.warning("BT correction returned a kind it cannot judge: %s", entry)
            return None
        findings.append(Finding(kind=kind, note=note[:1000], segment_id=segment_id))
    return CorrectionCheck(resolved=bool(parsed["resolved"]), findings=findings)


def correction_to_verify(
    state: BackTranslationState,
    told: list[IRSegment],
    retired: list[IRSegment],
) -> tuple[Finding, IRSegment, IRSegment] | None:
    """The finding, the stretch it was raised on, and the stretch that replaced it.

    One shape counts as a correction: the reading's own list of stretches, with exactly one
    position now held by a different row, and that position is the one the current finding
    names, and the row that stood there was superseded by the row standing there now.

    Everything else falls through to the full reading, which is the answer that is never wrong
    — only more expensive. That is deliberate, and it is what makes every awkward case safe
    without a rule of its own: a stretch divided changes the list's length; two corrections at
    once move two positions; a stretch retold that no finding pointed at moves a position that
    is not the finding's; a finding with no address names nothing to compare; a first reading
    has no earlier list at all; and a mother-tongue re-recording leaves a stretch with nothing
    told back, so the chain from the finding's stretch does not reach what stands there now.
    """
    finding = state.current_finding
    before = state.analysed_segment_ids
    if finding is None or finding.segment_id is None or before is None:
        return None

    now = [segment.id for segment in told]
    if len(before) != len(now):
        return None
    moved = [at for at, (was, stands) in enumerate(zip(before, now, strict=True)) if was != stands]
    if len(moved) != 1:
        return None

    position = moved[0]
    if before[position] != finding.segment_id:
        return None
    earlier = next((row for row in retired if row.id == finding.segment_id), None)
    if earlier is None or earlier.superseded_by_id != now[position]:
        return None

    corrected = told[position]
    if not (earlier.transcript or "").strip() or not (corrected.transcript or "").strip():
        return None
    return finding, earlier, corrected


def findings_after_correction(
    findings: list[Finding], check: CorrectionCheck, corrected: IRSegment
) -> list[Finding]:
    """What the team hears about next, once one correction has been verified.

    Answered, and the finding leaves; whatever the correction broke takes its place at the
    front, so the team is answered about the stretch they just retold rather than being sent
    somewhere else in the same breath.

    Unanswered, and it stays — but re-addressed to the stretch that now counts. Left pointing
    at the row it was raised on, it would send the team to a version that no longer exists, and
    the screen that shows them where the error lives would have nothing to show.

    What the correction broke is not added on top of a finding that still stands. Asking the
    team for two things about one stretch in one turn is how a room stops being followable, and
    the next round raises it again if it is still true.
    """
    if not check.resolved:
        return [findings[0].model_copy(update={"segment_id": corrected.id}), *findings[1:]]
    return [*check.findings, *findings[1:]]


async def verify_correction(
    *,
    finding: Finding,
    earlier: IRSegment,
    corrected: IRSegment,
    scope: str,
    pericope_num: str,
    correction_prompt: str,
    session_language: str = "Portuguese",
    settings: Settings | None = None,
) -> CorrectionCheck | None:
    """Ask whether one retold stretch answers the finding raised on it. Never voiced.

    Only this stretch is shown. The analyst's reading stays whole because its own definition of
    a missing element is *one that appears in no chunk* — a statement about the set, which a
    single stretch cannot support. This asks a different question, about a finding that is
    already known, and that question fits in one stretch.

    Returns None when the call or its reply failed, which is not the same as a correction that
    passed: the caller keeps the finding rather than dropping it on an outage.
    """
    cfg = settings or get_settings()
    system = render(
        correction_prompt,
        SESSION_LANGUAGE=session_language,
        SCOPE=scope,
        MEANING_MAP=load_map(pericope_num).body,
        FINDING=findings_block(finding),
        EARLIER_TELLING=earlier.transcript or "",
        NEW_TELLING=corrected.transcript or "",
    )
    try:
        raw = await call_agent(
            system_prompt=system,
            user_content="Verifique a correção contra o achado.",
            temperature=0.0,
            max_output_tokens=1500,
            settings=cfg,
        )
    except Exception:
        logger.exception("BT correction check failed for %s", pericope_num)
        return None
    return _parse_correction(raw, corrected.id)


def findings_block(finding: Finding | None) -> str:
    """Exactly one finding reaches the Speaker; the rest wait for the next round."""
    if finding is None:
        return "(nenhum achado — o contado de volta está completo)"
    return f"- {finding.kind}: {finding.note}"


#: What every closing below promises except `CLOSING_CHECKED`: the process goes on. It used
#: to be a static line in the prompt template itself, right under `{{CLOSING}}` and outside
#: any branch — true of every verdict turn there was, until `CLOSING_CHECKED` gave the
#: process an ending. Left there it would have sat right after "there is no next turn" and
#: said the opposite in the same breath, so it now lives inside each closing that still has
#: a next round instead, and not in the one that does not.
_NEXT_ROUND = "After the team acts on this one, they will finish the telling-back again."

CLOSING_ON_SCREEN = (
    """- End by handing the choice to the screen, not by asking for a spoken \
answer. This stretch is on screen with its two voices side by side: theirs, in their own \
language, and the telling in {session_language}. Ask the boundary question above, then in one \
short sentence tell them they can listen to both and tap the microphone of the voice that has \
to speak again. Do not ask them to say the answer out loud, and do not offer any other next \
step — the screen offers exactly those two, and naming a third promises something they cannot \
do. Remaining findings wait for the next round. """
    + _NEXT_ROUND
    + " Never a checklist, never a speech."
)

CLOSING_PLAIN = (
    "- End with exactly one answerable question or invitation. Remaining findings wait for "
    "the next round. " + _NEXT_ROUND + " Never a checklist, never a speech."
)
#: Word for word what this prompt closed with before the screen existed. A turn with no finding
#: at all affirms and names the badge; both other closings explain themselves in terms of *this
#: finding*, and there is none — `findings_block` is saying so in the same prompt.

CLOSING_CHECKED = """- Say plainly that the passage is told and checked, then stop there. Do \
not ask a question, do not invite them to answer anything, do not ask how the team feels, and \
do not say goodbye. There is no next turn on this passage — the screen takes the team on from \
here. Never a checklist, never a speech."""
#: The one turn with no finding that also has no next round: `state.checked` closes the
#: passage for good, so a question here would ask for an answer nobody will ever read — and,
#: unlike every other closing, this one may not carry `_NEXT_ROUND` either.

CLOSING_SPOKEN = (
    "- End with exactly one answerable question or invitation, and let them answer in words. "
    "This finding does not land on one stretch, so there is no stretch on screen and no two "
    "voices to choose between — the next conversational turn will respond to what they say. "
    "Remaining findings wait for the next round. "
    + _NEXT_ROUND
    + " Never a checklist, never a speech."
)

CLOSING_MISSING_ON_SCREEN = (
    "- End by handing the choice to the screen, not by asking for a spoken answer. This "
    "stretch is on screen, and something the passage has is not in it. In one short sentence, "
    "tell them they can listen to both voices and then record this part again — the whole "
    "part, what they already told and what was missing. The screen offers exactly one "
    "microphone for that; do not name a second one, and do not ask them to say the answer out "
    "loud. Remaining findings wait for the next round. "
    + _NEXT_ROUND
    + " Never a checklist, never a speech."
)

CLOSING_MISSING_TO_REHEARSAL = (
    "- End by handing the choice to the screen, not by asking for a spoken answer. The end of "
    "the story has not been told yet — nothing they recorded is wrong, and nothing they "
    "recorded will be lost. In one short sentence, tell them they can go on and record what "
    "is still missing, and that what they already recorded stays. The screen offers exactly "
    "one microphone for that. Do not offer to settle it later, do not ask them to choose "
    "between voices, and do not ask them to say anything out loud. "
    + _NEXT_ROUND
    + " Never a checklist, never a speech."
)


def closing_block(finding: Finding | None, *, checked: bool = False) -> str:
    """How the Speaker is told to end this turn: handing to the screen, or asking out loud.

    `checked` is the caller's `state.checked` — whether this turn, with no finding, is also
    the one that strikes the passage off the wheel for good. It only ever matters when
    `finding` is `None`: a turn with a finding is not the checked turn, whatever `checked`
    says, so the flag is read nowhere else in this function.

    Chosen here rather than by the Speaker reading a branch, because the finding carries the
    deciding fact and the prompt does not: `findings_block` sends kind and note, never the
    address. A prompt that branched would be asking a model not to promise a choice the screen
    will not offer; injecting one closing means the wrong instruction is never in front of it.

    What counts as a stretch to hand over is `points_at_a_stretch`, and it is not written out
    a second time here: the room's request for the whole stretch turns on the same answer, and
    two copies of it would be two things free to disagree about the same screen.

    A missing element is the one kind whose screen no longer matches the other two closings.
    On a stretch, the screen keeps both "listen" buttons but offers one microphone — record
    the part again, the whole part — so the closing that names a microphone per voice
    promises a choice that is not there. Off every stretch, the end of the story has simply
    not been told yet: the screen takes them on to record what is missing, keeping everything
    they recorded, and the closing that asks for a spoken answer promises a next
    conversational turn this path never has — it is where *"quer deixar para alinharmos mais
    na frente?"* came from. What the screen offers the other kinds without a stretch is a
    product decision still open, so they keep `CLOSING_SPOKEN` untouched.

    Returned with `{session_language}` still in it, for whoever fills the template to
    substitute from the same value it gives `{{SESSION_LANGUAGE}}`. Naming the language here
    would mean two defaults that agree by luck, and the day a caller passes a language to the
    turn the closing would go on saying Portuguese. It is not left as a `{{...}}` placeholder
    because `render` fills in one pass: one arriving inside an injected value is never seen
    again and reaches the model as literal braces.
    """
    if finding is None:
        return CLOSING_CHECKED if checked else CLOSING_PLAIN
    if finding.kind is FindingKind.MISSING:
        return (
            CLOSING_MISSING_ON_SCREEN
            if points_at_a_stretch(finding)
            else CLOSING_MISSING_TO_REHEARSAL
        )
    return CLOSING_ON_SCREEN if points_at_a_stretch(finding) else CLOSING_SPOKEN


def points_at_a_stretch(finding: Finding | None) -> bool:
    """Whether this finding puts one stretch on screen, with a microphone to speak it again.

    The deciding fact is not whether the finding has an address — it is whether a boundary
    question was asked. `unclear` names a stretch and still asks only for that piece again,
    and the screen exists to answer *"is it in your recording, or did it come in with the
    telling?"*. Where that question is not put, there is no choice to hand over.

    One expression, because two things now turn on it: which closing the Speaker is given,
    and whether the room asks for the whole stretch. They have to agree — the request is
    about the gesture the screen is offering, so a room that warned about a replacement the
    screen never offers would be describing work the team cannot do.
    """
    return (
        finding is not None
        and finding.segment_id is not None
        and finding.kind not in EVIDENCE_LIMIT_KINDS
    )


def with_the_whole_stretch_asked_for(
    speech: str,
    finding: Finding | None,
    language_code: str = FLOOR,
    *,
    used_fail_safe: bool = False,
) -> str:
    """The verdict, and after it the request to tell that whole stretch again.

    The correction the screen offers **replaces** one stretch: the new telling-back takes its
    position and the old one stops counting. A team that records only the amendment — which is
    what anybody would do — loses everything they had already told there. In a real session the
    same stretch was corrected three times and each round took the round before it out of
    circulation, with nothing saying so.

    So the room says it. Appended to the verdict rather than answered as a second clip: the
    response carries exactly one address for audio, and a sentence needing a slot of its own
    would need a new app release before a team could hear it at all. The team hears one turn,
    which is also what it is.

    Said only where the screen actually offers a microphone on that stretch — two for most
    findings, one for a missing element — which is what `points_at_a_stretch` decides:
    nothing is replaced anywhere else, and a correction instruction out of turn confuses more
    than it helps.

    A turn that fell back to a fail-safe carries nothing after it, and neither does one with
    nothing to carry. A fail-safe is played from inside the app by the name it is known by, so
    a sentence appended to one would reach the transcript and never the room; and a request
    with no verdict in front of it is an instruction the team was given no reason for.
    """
    if used_fail_safe or not speech or not points_at_a_stretch(finding):
        return speech
    asked = first(FailSafe.STRETCH_TO_CORRECT, language_code)
    return f"{speech} {asked}" if asked else speech
