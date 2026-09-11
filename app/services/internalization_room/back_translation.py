from __future__ import annotations

import enum
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.core.config import Settings, get_settings
from app.core.exceptions import UpstreamServiceError
from app.db.models.internalization_room import IRSegment
from app.models.internalization_room import PlayedTake
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.fail_safe import FailSafe, first
from app.services.internalization_room.languages import FLOOR, LANGUAGE_NAMES
from app.services.internalization_room.llm import analysis_ladder, call_agent
from app.services.internalization_room.render import render

logger = logging.getLogger(__name__)


class FindingKind(enum.StrEnum):
    MISSING = "missing"
    ADDITION = "addition"
    UNCLEAR = "unclear"


EVIDENCE_LIMIT_KINDS = frozenset({FindingKind.UNCLEAR})

#: The wire name a reply or a stored row may still carry, which is no finding at all: thin
#: evidence about a legible stretch does not stop the passage from being checked (ADR 0013).
_RETIRED_EVIDENCE_KIND = "insufficient_evidence"


def _is_the_retired_evidence_kind(entry: Any) -> bool:
    return isinstance(entry, dict) and entry.get("kind") == _RETIRED_EVIDENCE_KIND


def _without_the_retired_evidence_kind(data: Any) -> Any:
    """The findings of a stored row or a fresh reply, with the retired name taken out.

    The two stored containers validate through it, so a row written before the ruling opens
    with that finding gone from `findings` and from `superseded[].findings`. `BtAnalysis`
    does not: it is only ever built here, from findings this has already been over. A copy
    rather than a mutation, because the row it is handed is the session's own JSON column.
    """
    if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
        return data
    kept = [entry for entry in data["findings"] if not _is_the_retired_evidence_kind(entry)]
    return {**data, "findings": kept}


#: The wire name for a **Filled silence**. Her analyst's contract emits three kinds and marks
#: one inside the note, so the name is a request in the pending letter rather than something a
#: reading carries today; until it arrives the effective **Priority** starts one tier down. It
#: is read here and folded away, and the fact is kept as a flag on the finding.
_THE_NAME_FOR_A_FILLED_SILENCE = "silence"

_NAMES_READ_AS_ADDITION = frozenset(
    {
        _THE_NAME_FOR_A_FILLED_SILENCE,
        "meaning_change",
        "wrong_relation",
        "reordered_event",
        "preservation_violation",
    }
)


def _what_a_name_reads_as(kind_raw: str) -> str:
    return FindingKind.ADDITION.value if kind_raw in _NAMES_READ_AS_ADDITION else kind_raw


class Finding(BaseModel):
    kind: FindingKind
    note: str
    #: Which stretch the finding lands on, by the segment's own address. The team fixes one
    #: stretch of the recording, not the whole passage, so a finding that cannot name its
    #: stretch cannot be acted on. `None` when the analyst could not attribute it — the room
    #: then falls back to the whole clip, which is what it always did. Also `None` for a
    #: missing element the analyst places after everything the team told: there is no
    #: stretch to point at, so the room sends the team on to keep recording instead.
    #:
    #: It was the stretch's position in a list, which named nothing the moment the list
    #: changed. The analyst still answers with a number, because asking a model to echo an
    #: identifier back is trading a reliable field for one it can invent; the number is read
    #: as a position in the list that call was given and resolved to an address here, where
    #: it is already being validated.
    segment_id: str | None = None
    #: The frase number the analyst gave, kept beside the stretch it resolved to. `None` when
    #: the reply named no readable position, and on every row written before the field existed.
    #:
    #: The stretch alone cannot say which frase a finding is about: a missing element placed
    #: *after* frase N resolves to stretch N+1, so an addition on frase N and that missing
    #: element land on two different stretches while being one swap of one frase.
    chunk: int | None = None
    #: A **Filled silence**: the telling says something the passage keeps quiet on purpose.
    #: The top tier of the **Priority**, and the only thing that puts one addition above
    #: another. It decides the Priority and nothing else — the kind stays `addition` for the
    #: app, the packet, the golden scripts and the Speaker, and the withheld content is
    #: never named.
    fills_silence: bool = False
    #: Whether a Correction check raised it. What a mend broke is answered on the stretch the
    #: team just retold rather than behind whatever outranks it elsewhere, so the flag keeps
    #: the front for as long as the finding is on the list. The front used to be list
    #: position alone, which the Priority applied at the pick would have read straight past.
    raised_by_check: bool = False

    @model_validator(mode="before")
    @classmethod
    def _a_name_that_reads_as_addition(cls, data: Any) -> Any:
        """The wire name folded to the kind every consumer sees, the silence kept as a flag.

        One fold for a fresh reply and for a stored row, because the two are the same
        question asked in two places: after the collapse to three kinds a **Filled silence**
        *is* an addition, and nothing structured in a finding tells it from any other.

        A flag already set is never cleared. The state is a JSON column revalidated on every
        request, so a row written with it comes back naming `addition`, and a fold that read
        the name alone would take the silence out of the finding the moment it was stored.
        """
        if not isinstance(data, dict):
            return data
        raw = data.get("kind")
        if not isinstance(raw, str):
            return data
        return {
            **data,
            "kind": _what_a_name_reads_as(raw),
            "fills_silence": bool(data.get("fills_silence"))
            or raw == _THE_NAME_FOR_A_FILLED_SILENCE,
        }


class BtAnalysis(BaseModel):
    """One completed analyst pass."""

    findings: list[Finding] = Field(default_factory=list)


class SupersededAttempt(BaseModel):
    """A telling-back the team replaced by re-recording.

    Its findings do not disappear with the clip: they are the history the Refine artifact
    carries, clearly marked as superseded — the team's open questions survive their own
    retake. The stretches themselves are no longer copied in here; they are rows that stay
    exactly where they are, marked as no longer counting, and `retired_segments` reads them.
    """

    findings: list[Finding] = Field(default_factory=list)
    played_by_take: list[PlayedTake] = Field(default_factory=list)
    played_ranges: list[list[int]] = Field(default_factory=list)
    clip_duration_ms: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _thin_evidence_is_no_finding(cls, data: Any) -> Any:
        return _without_the_retired_evidence_kind(data)


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
    checked: bool = False
    superseded: list[SupersededAttempt] = Field(default_factory=list)
    #: What the team listened to, one entry per rehearsal part, each in that part's own
    #: milliseconds. This is the report, and the only one the gate reads: a part carries its own
    #: subject, so recording one part again loses the listening to that part and to nothing else.
    played_by_take: list[PlayedTake] = Field(default_factory=list)
    #: The shape the tablets in the field still send: one span list and one total over the parts
    #: glued together. Kept because it is the record of what that build reported, and read by
    #: nothing. Numbers with no subject say a clip was played through without saying which clip,
    #: so they went on reading as proof after the team threw that recording away and started the
    #: telling-back over on a new one (ADR 0017).
    played_ranges: list[list[int]] = Field(default_factory=list)
    clip_duration_ms: int | None = None
    #: Which rehearsal recordings the flat report above was stored against, stamped by the
    #: server from the stretches. It was the subject that report could not carry for itself,
    #: and it is not evidence either: it says which recordings existed when the report arrived,
    #: never that any of them was played. The gate does not consult it, and neither does
    #: anything else: it is kept because a row written before the parts were named carries it.
    played_take_ids: list[str] = Field(default_factory=list)
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
    #: the set. One thing lives only in the set — a correction can answer, by accident, a
    #: finding raised on another stretch — and `checked` strikes the passage off the wheel for
    #: good, with no undo.
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

    @model_validator(mode="before")
    @classmethod
    def _thin_evidence_is_no_finding(cls, data: Any) -> Any:
        """The retired name leaves the row, and the verdict it produced leaves with it.

        A row that stored that finding also stored the clip the Speaker said about it, and
        `terminei` serves a stored verdict rather than reading again. Dropping the finding
        and keeping the verdict left the team hearing *too little to check* on every press,
        about a frase the room no longer has anything to say about, until they recorded
        something. Without it the next press decides again on what the row still holds: no
        finding left is the checked closing, and a `missing` that survived the drop is
        voiced instead. The analyst is not asked again — the reading it already did stands.
        """
        without = _without_the_retired_evidence_kind(data)
        if without is data or len(without["findings"]) == len(data["findings"]):
            return without
        return {**without, "verdict": None}

    def already_analysed(self, segments: list[IRSegment]) -> bool:
        return self.analysed_segment_ids is not None and self.analysed_segment_ids == [
            segment.id for segment in segments
        ]

    @property
    def never_analysed(self) -> bool:
        """The analyst has not read this telling-back at all.

        Distinct from `not already_analysed`, which is also true when more was told back
        after the last pass. Never read is the state whose default — no findings — is
        indistinguishable from a clean check.
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


def playback_confirms_rehearsal(
    state: BackTranslationState, rehearsal_take_ids: list[str]
) -> list[str]:
    """Which parts of the rehearsal the team has no evidence of having heard, sorted.

    Empty is heard. The question is asked once per part and answered per part, because that is
    how the team listens: a part is its own recording, and recording one again says nothing
    about the others. Asked of the whole passage instead, one retake threw away the listening
    to every part at once, and the answer could never say which part to send the team back to.

    A part is heard when an entry names it and that entry reaches the end of *that part's* own
    length. Both numbers are required rather than either: a length with nothing played is a
    report that the team played nothing at all, and spans with no length cannot be checked
    against anything. The arithmetic itself answers True to both of those — an absent report is
    not a short one, which is not its question — so the two are asked here, where they are.

    Entries naming recordings the stretches no longer name are ignored rather than refused.
    They are the residue of a part the team recorded again, about audio no stretch is a slice
    of any more; refusing on them would refuse a rehearsal that was in fact heard whole.

    The flat report beside this one is never consulted, and neither is the server-stamped
    subject. A report we cannot tie to a recording is not evidence about any recording, so a
    row written before the parts were named names every part and the team plays it through
    again (ADR 0017).
    """
    heard = {
        entry.take_id
        for entry in state.played_by_take
        if entry.played_ranges
        and entry.clip_duration_ms
        and played_ranges_cover_clip(entry.played_ranges, entry.clip_duration_ms)
    }
    return sorted(set(rehearsal_take_ids) - heard)


#: What `segments_block` carries when nothing has been told back yet, in the session's own
#: language. Keyed by the language code, in the shape the other per-language tables use — an
#: unclaimed language falls back to the authored English line.
_NOTHING_TOLD_BACK_YET: dict[str, str] = {
    "pt": "(a equipe ainda não traduziu nada)",
    "en": "(the team has not translated anything yet)",
    "es": "(el equipo aún no ha traducido nada)",
}


def segments_block(segments: list[IRSegment], language_code: str = FLOOR) -> str:
    """The stretches as the analyst reads them: numbered, in the order the team told them.

    Numbered from one over the list it is given, so the number is a position in *this* call
    and never an identifier the analyst has to keep. `_segment_pointed_at` reads it back the
    same way.

    `language_code` only governs the empty-telling-back placeholder: the segments themselves
    are the team's own words, verbatim, in whatever language they spoke.
    """
    if not segments:
        return _NOTHING_TOLD_BACK_YET.get(language_code, _NOTHING_TOLD_BACK_YET[FLOOR])
    return "\n".join(
        f"{position}. {segment.transcript}" for position, segment in enumerate(segments, start=1)
    )


def _refused(condition: str, raw: str, session: str) -> None:
    """Every refusal leaves the reply behind it, whole, with the condition that refused.

    They used to return None in silence. A reply the model did
    produce was then indistinguishable from one it never did, and the night of 2026-09-01
    was spent unable to say what the analyst had answered. The reply is logged whole
    rather than cut at a few hundred characters: it is bounded by the call's output cap,
    and a truncated reply is exactly what could not be diagnosed. The session is named so
    the line can be tied to the request that got the 502, across replicas and teams.
    """
    logger.warning("BT analyst reply refused (%s) for session %s: %s", condition, session, raw)


def _dropped(entries: list[Any], raw: str, about: str) -> None:
    """A name the room retired left the reply, and the rest of it was read.

    Said only once the reading has been accepted: a reply carrying the retired name beside
    a malformed entry is refused, and announcing a drop it then threw away with everything
    else would send the next investigation to the wrong place. Its own line rather than
    `_refused`'s for the same reason, and the reply is behind it whole, as every refusal
    carries one.
    """
    if not any(_is_the_retired_evidence_kind(entry) for entry in entries):
        return
    logger.warning(
        "BT reply named %s, which is no finding; dropped it and read the rest (%s): %s",
        _RETIRED_EVIDENCE_KIND,
        about,
        raw,
    )


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

    Whatever the reply says about how much evidence it had is not read: the flag that used
    to gate the conferral is gone, and a reply that still carries it is read with the key
    ignored. An entry naming the retired evidence kind is dropped and the rest of the reply
    kept, because refusing a reply whole over a name the prompt itself stopped offering is
    the ENG-719 failure with a different trigger — a team stopped three times by a round
    with no verdict, for a reading the room could have used.
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

    reported = parsed["findings"]

    findings: list[Finding] = []
    for entry in [one for one in reported if not _is_the_retired_evidence_kind(one)]:
        if not isinstance(entry, dict):
            _refused("an entry in findings is not an object", raw, session)
            return None
        wire_name = str(entry.get("kind", ""))
        kind_raw = _what_a_name_reads_as(wire_name)
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
            Finding.model_validate(
                {
                    "kind": wire_name,
                    "note": note[:1000],
                    "chunk": _chunk_named(entry.get("chunk"), segments),
                    "segment_id": _segment_pointed_at(
                        entry.get("chunk"),
                        segments,
                        kind=kind,
                        where=entry.get("where"),
                        raw_reply=raw,
                        session=_session_of(segments),
                    ),
                }
            )
        )

    _dropped(reported, raw, f"session {session}")
    return BtAnalysis(findings=findings)


def _log_accepted_reading(
    *,
    session_id: str,
    reading: str,
    raw: str,
    findings: list[Finding],
    segment_id: str | None = None,
    resolved: bool | None = None,
) -> None:
    """An accepted reading leaves a trace — what the model said, never what the team said.

    ``raw`` is the model's own reply, kept whole in the message; nothing from the team's
    transcript is read into `extra` or the message here, only what the model answered and
    the addresses that answer lands on. The counterpart to the refusal warnings already in
    this file (unparseable JSON, an unknown kind): those fire when a reply cannot be
    trusted at all, this fires once it has been trusted and parsed.
    """
    extra: dict[str, Any] = {
        "session_id": session_id,
        "reading": reading,
        "findings": len(findings),
    }
    if segment_id is not None:
        extra["segment_id"] = segment_id
    if resolved is not None:
        extra["resolved"] = resolved
    logger.info("BT %s reading accepted: %s", reading, raw, extra=extra)


_VALID_WHERE = frozenset({"before", "inside", "after"})


def _chunk_named(raw: Any, segments: list[IRSegment]) -> int | None:
    """The frase the analyst named, as a position in the reading it was given, or None.

    The validation `_segment_pointed_at` makes before it resolves an address, asked on its
    own because the two answers are not the same one: a missing element placed after frase N
    names frase N and resolves to the stretch after it, and one placed after the last frase
    names that frase and resolves to no stretch at all.
    """
    if isinstance(raw, bool) or not isinstance(raw, int | str):
        return None
    try:
        position = int(raw)
    except ValueError:
        return None
    return position if 1 <= position <= len(segments) else None


def _segment_pointed_at(
    raw: Any,
    segments: list[IRSegment],
    *,
    kind: FindingKind,
    where: Any = None,
    raw_reply: str = "",
    session: str = "?",
) -> str | None:
    """Which stretch the finding lands on, by address, or None when it names none.

    The analyst answers with the position it was given, and the position is turned into an
    address here — the one place that already decides whether the pointer can be trusted. A
    finding the team cannot locate sends them back to the whole recording, so a pointer that
    is not a number, or names a stretch that is not in this reading, degrades to that rather
    than to a stretch that does not exist.

    For a `missing` finding the analyst also names `where` the missing content sits relative
    to the chunk it gave: `"after"` on the *last* chunk means nothing is missing inside any
    chunk — it is missing past all of them, with no chunk to point at — so this returns
    `None`, exactly as a `null` chunk always has. `"after"` short of the last chunk moves the
    pointer forward one, because a thing missing after chunk k is missing at the start of
    chunk k+1. `"before"` and `"inside"` both land on the named chunk itself, which is also
    where an absent or unrecognised `where` falls back to — the table this resolves is the
    product owner's, not a guess the parser is free to make on an unfamiliar value; an
    unrecognised one is logged with what it was rather than silently swallowed.

    `where` is read only when `kind` is `missing`: every other kind is a statement about the
    chunk itself, so a `where` alongside one is ignored without comment.
    """
    position = _chunk_named(raw, segments)
    if position is None:
        return None

    if kind is FindingKind.MISSING and where is not None:
        if not isinstance(where, str) or where not in _VALID_WHERE:
            _refused(f"unrecognised where {where!r}", raw_reply, session)
        elif where == "after":
            return None if position == len(segments) else segments[position].id

    return segments[position - 1].id


async def analyse_telling_back(
    *,
    segments: list[IRSegment],
    scope: str,
    pericope_num: str,
    analyst_prompt: str,
    session_language: str = LANGUAGE_NAMES[FLOOR],
    language_code: str = FLOOR,
    settings: Settings | None = None,
    session_id: str = "",
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
        SEGMENTS=segments_block(segments, language_code),
    )
    try:
        raw = await call_agent(
            system_prompt=system,
            user_content="Compare a tradução com o mapa.",
            ladder=analysis_ladder(cfg),
            max_output_tokens=4096,
            settings=cfg,
        )
    except Exception as failure:
        logger.exception("BT analysis failed for %s", pericope_num)
        raise UpstreamServiceError("a análise da tradução não pôde ser feita agora") from failure
    analysis = _parse_analysis(raw, segments)
    if analysis is not None:
        _log_accepted_reading(
            session_id=session_id, reading="analysis", raw=raw, findings=analysis.findings
        )
    return analysis


class CorrectionCheck(BaseModel):
    """One verification of one corrected stretch.

    ``resolved`` and ``findings`` are independent on purpose: a correction can answer the
    finding it was asked about and still drop an element only that stretch carried, and it can
    leave the finding standing while breaking nothing. Collapsing them into one verdict would
    make the room unable to tell the team which of the two happened.

    ``findings`` is what the room decided, not a copy of what the reader wrote: the losses the
    reader's own count implies are already in it, and the ones it said twice are in it once.
    The count itself is not carried here — nothing downstream asks what was enumerated, only
    what it means for this stretch, and a field nobody reads is one more thing to keep true.
    """

    resolved: bool
    findings: list[Finding] = Field(default_factory=list)


#: What the verification may report. Deliberately short of the analyst's list: `missing` here
#: means *this stretch said it before and does not now*, never the analyst's global sense.
CORRECTION_KINDS = frozenset({FindingKind.MISSING, FindingKind.ADDITION, FindingKind.UNCLEAR})


#: A word long enough to carry meaning rather than grammar. The dedupe below asks whether a
#: reported note names the element the count marked lost, and a note that repeats the element's
#: words will not reliably repeat its prepositions — requiring them would stop it ever firing.
_CONTENT_WORD = re.compile(r"[^\W\d_]{4,}")


def _content_words(text: str) -> set[str]:
    """The words of a phrase that carry it, folded so two spellings of one word still match.

    Accents are stripped rather than compared: the note and the count are both written by a
    model, in a language it is retelling into, and one of the two spelling `sepultada` with a
    stray accent must not make the room ask the team about the same loss twice.
    """
    folded = unicodedata.normalize("NFKD", text.casefold())
    return set(_CONTENT_WORD.findall("".join(ch for ch in folded if not unicodedata.combining(ch))))


def _elements_the_count_lost(raw: Any) -> list[str] | None:
    """The elements the count marks as no longer told, or None when the count cannot be read.

    None and an empty list must stay apart: empty is "counted, and nothing fell", which is a
    clean stretch, and None is "there is no count here to read", which is not — it leaves
    whatever the reader reported standing and says so in the log. Read atomically for the same
    reason the two parsers around it are: half a count is a check the room believes it is
    running and is not, and the element it skipped is the one nobody is ever asked about.
    """
    if not isinstance(raw, list):
        logger.warning("BT correction returned an enumeration that is not a list: %.200r", raw)
        return None
    lost: list[str] = []
    for entry in raw:
        if not isinstance(entry, dict) or not isinstance(entry.get("still_told"), bool):
            logger.warning("BT correction enumerated an element without a verdict: %.200r", entry)
            return None
        element = str(entry.get("element", "")).strip()
        if not element:
            logger.warning("BT correction enumerated an element with no name: %.200r", entry)
            return None
        if not entry["still_told"]:
            lost.append(element)
    return lost


def _elements_brought_back(raw: Any) -> list[str]:
    """Elements the map gives that the new telling states and the earlier one did not.

    Lenient, unlike `_elements_the_count_lost`: this list is the mechanical backstop over the
    prompt's own `Added` rule, not the count the room depends on, so a reply that omits it or
    gets its shape wrong just goes without the backstop rather than losing the whole
    verification over a field nothing here requires.
    """
    if not isinstance(raw, list):
        return []
    elements: list[str] = []
    for entry in raw:
        if isinstance(entry, str):
            element = entry.strip()
        elif isinstance(entry, dict):
            element = str(entry.get("element", "")).strip()
        else:
            continue
        if element:
            elements.append(element)
    return elements


def _is_the_correction_arriving(finding: Finding, brought_back: list[str]) -> bool:
    """Whether a reported addition is actually one of the elements the correction brought back.

    The same subset-of-content-words test `_already_reported` uses for a derived loss, mirrored
    for the opposite mistake: the prompt's `Added` rule already tells the reader an element the
    map gives is never an addition, and this is the backstop for when it reports one anyway.
    """
    if finding.kind is not FindingKind.ADDITION:
        return False
    note_words = _content_words(finding.note)
    for element in brought_back:
        words = _content_words(element)
        if words and words <= note_words:
            return True
    return False


def _already_reported(element: str, reported: list[Finding]) -> bool:
    """Whether a loss the reader wrote out already names the element the count marked lost.

    One loss is one thing to mend, however many times the reader said it. Covered means the
    note carries every word of the element that carries meaning — deliberately strict, because
    the two mistakes are not equal: counting one loss twice asks the team about a clause they
    already mended, and suppressing a real one means they are never asked at all.

    An element with no such word covers nothing. Left alone it would be the empty set, which
    every note contains, and the room would silently drop every loss it counted.
    """
    words = _content_words(element)
    if not words:
        return False
    return any(
        finding.kind is FindingKind.MISSING and words <= _content_words(finding.note)
        for finding in reported
    )


def _parse_correction(raw: str, segment_id: str, chunk: int) -> CorrectionCheck | None:
    """The verification's reply, or None when it cannot be trusted at all.

    None is never "the correction was fine": a verification that did not happen must not be
    readable as one that passed, because a finding dropped on an unparseable reply is a finding
    the team is never asked about again. Read atomically for the same reason `_parse_analysis`
    is — one malformed entry among good ones would otherwise silently shrink the report.

    Every finding is stamped with the corrected stretch's own address, and with the frase that
    stretch now holds: the verification looked at exactly one stretch, so there is nowhere else
    its findings could land, and a finding the team cannot locate sends them back to the whole
    recording for no reason. The frase is what lets a swap the mend itself introduced — a
    clause dropped and an outside detail brought in, on the stretch just retold — reach the
    team as one thing, the same as one the analyst raised.

    A loss is derived from the count rather than waited for. `carried` is the reader's
    enumeration of what the earlier telling of this stretch stated, entry by entry, and an
    entry marked as no longer told **is** a loss here — whether or not the reader also wrote it
    out under `findings`. Asked holistically, a reader confirms what is present far better than
    it notices what is absent, which is how a stretch retold to answer one finding came back
    without a clause and was reported as nothing at all; enumerating first is what the room
    now depends on, and depending on the reader to volunteer the same loss twice would put the
    old failure back. `_already_reported` is why saying it twice still costs the team one mend.

    A reply with no `carried` at all is a stored prompt that predates the count, and is read
    exactly as it always was: the room upgrades its prompts by editing a row, so the two shapes
    are in the air at the same time and the older one must not start reading as a clean stretch.

    `brought_back` is the mirror of `carried`, and lenient where `carried` is strict: an element
    the map gives that only the new telling states is the correction arriving, never an
    addition, and this is the backstop for a reader that reports one as `"addition"` anyway
    despite what the prompt's own `Added` rule already tells it. Absent or malformed, it is
    simply not applied — it stands over an existing rule rather than replacing it.
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
    for entry in [one for one in raw_findings if not _is_the_retired_evidence_kind(one)]:
        if not isinstance(entry, dict):
            return None
        note = str(entry.get("note", "")).strip()
        if not note:
            return None
        wire_name = str(entry.get("kind", ""))
        try:
            kind = FindingKind(_what_a_name_reads_as(wire_name))
        except ValueError:
            logger.warning("BT correction returned an unknown finding kind: %s", entry)
            return None
        if kind not in CORRECTION_KINDS:
            logger.warning("BT correction returned a kind it cannot judge: %s", entry)
            return None
        findings.append(
            Finding.model_validate(
                {
                    "kind": wire_name,
                    "note": note[:1000],
                    "segment_id": segment_id,
                    "chunk": chunk,
                    "raised_by_check": True,
                }
            )
        )

    brought_back = _elements_brought_back(parsed.get("brought_back"))
    if brought_back:
        findings = [f for f in findings if not _is_the_correction_arriving(f, brought_back)]

    if "carried" in parsed:
        lost = _elements_the_count_lost(parsed["carried"])
        reported = list(findings)
        findings.extend(
            Finding(
                kind=FindingKind.MISSING,
                note=element[:1000],
                segment_id=segment_id,
                chunk=chunk,
                raised_by_check=True,
            )
            for element in lost or []
            if not _already_reported(element, reported)
        )
    _dropped(raw_findings, raw, f"segment {segment_id}")
    return CorrectionCheck(resolved=bool(parsed["resolved"]), findings=findings)


@dataclass(frozen=True)
class CorrectionToVerify:
    """One retelling to check: what it answers, what it replaced, and where it now sits.

    `findings` is everything this turn is about, which is one finding or the two halves of one
    swap; `chunk` is the frase the corrected stretch holds in the reading as it stands, so a
    finding the check raises on it can be half of a swap in its turn.
    """

    findings: list[Finding]
    earlier: IRSegment
    corrected: IRSegment
    chunk: int


def correction_to_verify(
    state: BackTranslationState,
    told: list[IRSegment],
    retired: list[IRSegment],
) -> CorrectionToVerify | None:
    """What the retelling answers, the stretch it was raised on, and the stretch replacing it.

    One shape counts as a correction: the reading's own list of stretches, with exactly one
    position now held by a different row, and that position is the one the finding that leads
    names, and the row that stood there was superseded by the row standing there now.

    Everything else falls through to the full reading, which is the answer that is never wrong
    — only more expensive. That is deliberate, and it is what makes every awkward case safe
    without a rule of its own: a stretch divided changes the list's length; two corrections at
    once move two positions; a stretch retold that no finding pointed at moves a position that
    is not the finding's; a finding with no address names nothing to compare; a first reading
    has no earlier list at all; and a mother-tongue re-recording leaves a stretch with nothing
    told back, so the chain from the finding's stretch does not reach what stands there now.
    """
    answered = current_findings(state)
    finding = answered[0] if answered else None
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
    return CorrectionToVerify(answered, earlier, corrected, position + 1)


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

    A swap leaves and stays whole. One retelling was asked for and one answer came back about
    it, so clearing the addition and leaving the missing element behind would raise that half
    again next round and cost the team a second recording of the same scene — which is the
    defect the pair exists to spare them.

    What the correction broke is not added on top of a finding that still stands. Asking the
    team for two things about one stretch in one turn is how a room stops being followable, and
    the next round raises it again if it is still true.
    """
    answered = _the_current_swap(findings)
    if not check.resolved:
        return [
            finding.model_copy(update={"segment_id": corrected.id}) if at in answered else finding
            for at, finding in enumerate(findings)
        ]
    return [*check.findings, *(one for at, one in enumerate(findings) if at not in answered)]


async def verify_correction(
    *,
    findings: list[Finding],
    earlier: IRSegment,
    corrected: IRSegment,
    chunk: int,
    scope: str,
    pericope_num: str,
    correction_prompt: str,
    session_language: str = "Portuguese",
    settings: Settings | None = None,
    session_id: str = "",
) -> CorrectionCheck | None:
    """Ask whether one retold stretch answers what was raised on it. Never voiced.

    A swap goes in as the two lines it is, and one answer comes back for both: the retelling
    mends it only when the addition is gone from it *and* the missing element is in it. Shown
    only the addition, the check would pass a retelling that dropped the cause the team put in
    and still never told what the story tells in its place.

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
        FINDING=findings_block(findings),
        EARLIER_TELLING=earlier.transcript or "",
        NEW_TELLING=corrected.transcript or "",
    )
    try:
        raw = await call_agent(
            system_prompt=system,
            user_content="Verifique a correção contra o achado.",
            ladder=analysis_ladder(cfg),
            max_output_tokens=4096,
            settings=cfg,
        )
    except Exception:
        logger.exception("BT correction check failed for %s", pericope_num)
        return None
    check = _parse_correction(raw, corrected.id, chunk)
    if check is not None:
        _log_accepted_reading(
            session_id=session_id,
            reading="correction",
            raw=raw,
            findings=check.findings,
            segment_id=corrected.id,
            resolved=check.resolved,
        )
    return check


def _lands_on_a_frase(finding: Finding) -> bool:
    """Whether a finding can be half of a swap: it names a frase and a stretch to record.

    A missing element placed after everything told names the last frase and no stretch of its
    own (ADR 0007): the team records what is still missing and goes back to the rehearsal,
    erasing nothing. Joined to an addition on that frase, the turn would promise the two
    microphones of a stretch that is not there, and ask for one fix for two different walks.
    """
    return finding.chunk is not None and points_at_a_stretch(finding)


def _swaps(findings: list[Finding]) -> list[tuple[int, int]]:
    """Where an addition and a missing element on one frase sit, the addition first.

    Keyed on the frase the analyst numbered and not on the stretch each half resolved to: a
    missing element placed *after* frase N sits at the start of stretch N+1, so the two
    halves of one swap land on two different stretches while being one thing the team did.

    Each half is spoken for once. Two additions on a frase that carries one missing element
    are one swap and one addition left over, never two swaps over the same absence.
    """
    spoken_for: set[int] = set()
    swaps: list[tuple[int, int]] = []
    for at, finding in enumerate(findings):
        if finding.kind is not FindingKind.ADDITION or not _lands_on_a_frase(finding):
            continue
        other = next(
            (
                index
                for index, candidate in enumerate(findings)
                if index not in spoken_for
                and candidate.kind is FindingKind.MISSING
                and _lands_on_a_frase(candidate)
                and candidate.chunk == finding.chunk
            ),
            None,
        )
        if other is not None:
            spoken_for.add(other)
            swaps.append((at, other))
    return swaps


#: The **Priority**, as Marcia wrote it correcting the P02 example: *silêncio preenchido >
#: outro acréscimo > falta > pouco claro*. A **Filled silence** is an addition whose flag is
#: set, so the top tier is not a kind and cannot be keyed off this table alone.
_PRIORITY = {FindingKind.ADDITION: 1, FindingKind.MISSING: 2, FindingKind.UNCLEAR: 3}
_A_FILLED_SILENCE = 0


def _tiers(findings: list[Finding]) -> list[int]:
    """Where each finding sits in the **Priority**, each swap taking its addition's tier.

    A swap is one thing the team did, and the addition is the half that names the stretch.
    Read as two findings, a swap would sink below every lone addition and the team would be
    sent elsewhere in the middle of one mistake.

    The top tier asks the kind as well as the flag. A **Filled silence** is an addition and
    nothing else, and the flag reaches this from a stored row: read off the flag alone, a
    row that somehow carried it on a missing element would put a missing element above
    every addition there is, which is a tier the Priority does not have.
    """
    tier_of = [
        _A_FILLED_SILENCE
        if finding.kind is FindingKind.ADDITION and finding.fills_silence
        else _PRIORITY[finding.kind]
        for finding in findings
    ]
    for addition, missing in _swaps(findings):
        tier_of[missing] = tier_of[addition]
    return tier_of


def the_index_that_leads(findings: list[Finding]) -> int | None:
    """Which finding this turn is about, before any swap is looked for.

    A Correction check's findings first, because what a mend broke is about the stretch the
    team just retold: sent elsewhere in the same breath, they answer a question about a part
    they are not looking at, and the stretch they are working on stays open behind them.
    That precedence used to be list position and nothing else, which is why it is a flag now
    — the Priority applied over the whole list reads straight past a position.

    The flag decides *who competes*, never who wins. One check answers about one stretch and
    can still come back with more than one thing — it reports what it saw, and the room
    derives a loss from the count on top of that — so the Priority rules inside its own reply
    as it does anywhere else. It is suspended against findings the check did not raise, and
    against nothing else.

    Then the **Priority**, ties in the analyst's own order. It is over the tiers and says
    nothing inside one, so reaching for a second key here — the frase, the stretch, the
    length of the note — would be the room inventing a precedence Marcia never ruled.

    At the pick and never at parse or storage. `state.findings` is what the packet, the
    resume and the correction check all read, and a list reordered on the way in would carry
    the Priority into every one of them and take a check's finding away from the front. Pure
    over the list for the same reason: the fresh verdict, the stored-verdict replay and the
    resume payload each recompute the pick, and three answers that could differ is a team
    hearing about one frase while the screen rebuilds on another.

    The one place that says which finding leads — a second expression of this would be a
    second thing free to answer it.
    """
    if not findings:
        return None
    competing = [at for at, finding in enumerate(findings) if finding.raised_by_check] or range(
        len(findings)
    )
    tier_of = _tiers(findings)
    return min(competing, key=lambda at: (tier_of[at], at))


def _the_current_swap(findings: list[Finding]) -> list[int]:
    """Which of the findings this turn is about: the one that leads, and its other half.

    The pick decides *whether* there is a swap. What this rule decides is the other half,
    and which of the two leads.
    """
    leads = the_index_that_leads(findings)
    if leads is None:
        return []
    for addition, missing in _swaps(findings):
        if leads in (addition, missing):
            return [addition, missing]
    return [leads]


def current_findings(state: BackTranslationState) -> list[Finding]:
    """What the Speaker is allowed to voice this turn: one finding, or one swap of one frase.

    An addition and a missing element on the same frase are one thing for the team — the
    telling put something in and dropped what the story tells in its place — so they are one
    thing to say, one fix to ask for and one retelling to check. Raised one at a time, the
    team records that part again for the addition and, the round after, records the same part
    again for the missing element.

    The addition leads, whichever of the two the analyst listed first: it is the half that
    names the stretch where the swap happened, so the closing, the request for the whole
    stretch and the stretch the screen puts up all name the same one. Led by a missing
    element placed after that frase, they would name the stretch after the swap instead.
    """
    return [state.findings[at] for at in _the_current_swap(state.findings)]


def the_finding_that_leads(state: BackTranslationState) -> Finding | None:
    """The half of this turn that carries its address, or None when there is nothing to say.

    The one finding, or the addition of a swap. It is what the closing, the request for the
    whole stretch and the stretch the screen puts up are all decided by, so that the three of
    them name the same one.
    """
    leading = current_findings(state)
    return leading[0] if leading else None


def findings_remaining(findings: list[Finding]) -> int:
    """How many things the team still has to act on, counted over the whole list.

    A swap is one of them wherever its two halves sit: the count is what tells the team how
    much of the round is still ahead of them, and a swap costs them one stop, not two.
    """
    return len(findings) - len(_swaps(findings))


def findings_block(findings: list[Finding]) -> str:
    """What reaches the Speaker this turn; the rest wait for the next round."""
    if not findings:
        return "(nenhum achado — a tradução está completa)"
    return "\n".join(f"- {finding.kind}: {finding.note}" for finding in findings)


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

CLOSING_MISSING_TO_REHEARSAL = (
    "- End by handing the choice to the screen, not by asking for a spoken answer. The end of "
    "the story has not been told yet — nothing they recorded is wrong, and nothing they "
    "recorded will be lost. In one or two short sentences, tell them to record what is still "
    "missing with the big microphone, and that when they finish they tap the green button to "
    "come back and check it. Do not offer to settle it later, do not ask them to choose "
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

    A missing element off every stretch is the one kind whose screen still differs from the
    rest: the end of the story has simply not been told yet, so the screen takes them on to
    record what is missing, keeping everything they recorded, and the closing that asks for a
    spoken answer promises a next conversational turn this path never has — it is where
    *"quer deixar para alinharmos mais na frente?"* came from. On a stretch, a missing element
    gets the same two microphones as every other finding there (decision of 2026-09-03,
    reversing ENG-710): the sibling closing that once named one microphone for it is gone.
    What the screen offers the other kinds without a stretch is a product decision still open,
    so they keep `CLOSING_SPOKEN` untouched.

    Returned with `{session_language}` still in it, for whoever fills the template to
    substitute from the same value it gives `{{SESSION_LANGUAGE}}`. Naming the language here
    would mean two defaults that agree by luck, and the day a caller passes a language to the
    turn the closing would go on saying Portuguese. It is not left as a `{{...}}` placeholder
    because `render` fills in one pass: one arriving inside an injected value is never seen
    again and reaches the model as literal braces.
    """
    if finding is None:
        return CLOSING_CHECKED if checked else CLOSING_PLAIN
    if finding.kind is FindingKind.MISSING and not points_at_a_stretch(finding):
        return CLOSING_MISSING_TO_REHEARSAL
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

    Said only where the screen actually offers a microphone on that stretch — two, for every
    finding that lands on one — which is what `points_at_a_stretch` decides: nothing is
    replaced anywhere else, and a correction instruction out of turn confuses more than it
    helps.

    A turn that fell back to a fail-safe carries nothing after it, and neither does one with
    nothing to carry. A fail-safe is played from inside the app by the name it is known by, so
    a sentence appended to one would reach the transcript and never the room; and a request
    with no verdict in front of it is an instruction the team was given no reason for.
    """
    if used_fail_safe or not speech or not points_at_a_stretch(finding):
        return speech
    asked = first(FailSafe.STRETCH_TO_CORRECT, language_code)
    return f"{speech} {asked}" if asked else speech
