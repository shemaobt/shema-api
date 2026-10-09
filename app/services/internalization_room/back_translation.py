from __future__ import annotations

import enum
import json
import logging
import re
import unicodedata
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.core.config import Settings, get_settings
from app.core.exceptions import UpstreamServiceError
from app.db.models.internalization_room import IRSegment, IRTake
from app.models.internalization_room import PlayedTake
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.languages import FLOOR, LANGUAGE_NAMES
from app.services.internalization_room.llm import analysis_ladder
from app.services.internalization_room.part_names import Addresses
from app.services.internalization_room.prompt_blocks import validator_map_block
from app.services.internalization_room.render import render
from app.services.internalization_room.room_agent import room_agent

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


def _is_a_nuance(entry: Any) -> bool:
    return isinstance(entry, dict) and entry.get("kind") == "nuance"


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


class Nuance(BaseModel):
    note: str
    chunk: int
    segment_id: str
    quote: str
    story: str


class BtAnalysis(BaseModel):
    """One completed analyst pass."""

    findings: list[Finding] = Field(default_factory=list)
    nuances: list[Nuance] = Field(default_factory=list)


class ReadAhead(BtAnalysis):
    segment_ids: list[str]


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
    #: When the check last ran, stamped where `checked` is stamped: at the verdict, clean or
    #: not. It is not when it came out clean — a team that came out with a finding also has an
    #: answer to when the analyst last read them, and that is the question the packet's
    #: `lastCheckAt` asks.
    #:
    #: `None` for a telling-back no verdict has reached, and for every row written before this
    #: field existed: the state is a JSON column revalidated on every request, so an older row
    #: loads with it absent and nothing was migrated (the precedent `chunk` set). No route
    #: starts a whole telling-back over yet — `retire_every_segment` and `superseded` are
    #: written only by tests — so nothing clears this today. Recording one part again
    #: (`sessions.retire_the_part_recorded_again`, from the take upload) sets `checked` back
    #: to false and leaves this standing: the analyst did last read the team then, which is
    #: what `lastCheckAt` asks, so the packet shows `checked: false` beside that moment until
    #: the next verdict stamps a new one.
    checked_at: datetime | None = None
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
    #:
    #: Read leniently, where the door above is strict. Nothing measures this pair — the covering
    #: arithmetic is asked of `played_by_take` and of nothing else — so a shape it cannot use is
    #: no danger here, while refusing it on the way out of the database would stop a row written
    #: by an older build from loading on every route of that session.
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
    #: What the room said when it last reached a verdict, so a press that decides nothing new
    #: can hand back the same answer without voicing it again. `None` until a verdict has been
    #: spoken *and* stored, which is what separates "already judged" from a press that reached
    #: the analyst and then failed before the team heard anything — that one saves nothing at
    #: all, and the press after it does the whole turn.
    verdict: VoicedVerdict | None = None
    read_ahead: ReadAhead | None = None

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

    def read_ahead_of(self, segments: list[IRSegment]) -> ReadAhead | None:
        if self.read_ahead is None or self.read_ahead.segment_ids != [
            segment.id for segment in segments
        ]:
            return None
        return self.read_ahead

    @property
    def never_analysed(self) -> bool:
        """The analyst has not read this telling-back at all.

        Distinct from `not already_analysed`, which is also true when more was told back
        after the last pass. Never read is the state whose default — no findings — is
        indistinguishable from a clean check.
        """
        return self.analysed_segment_ids is None


PLAYBACK_TOLERANCE_MS = 750


def played_ranges_cover_clip(
    played_ranges: list[tuple[int, int]], clip_duration_ms: int | None
) -> bool:
    """Whether the reported playback reached the whole clip, within tolerance.

    A telling-back is a check of what was actually heard, not of what the team remembers,
    so "checked" over a half-listened clip would be a claim about audio nobody played.
    Reported ranges are merged and must cover [0, duration] with at most 750 ms of slack
    at either edge or between stretches. This is the arithmetic only: an absent report is
    not a short one, so it is not this function's to judge and comes back True. Whether a
    report exists at all, and whether it is about the recording still in play, is
    `unheard_parts`, which is what the release gate asks.

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


def rehearsed_parts(stretches: list[IRSegment]) -> list[str]:
    """The parts of the rehearsal the current stretches are slices of, sorted.

    The subject of the listening question, and the one both askers have to agree on: the check
    refuses on it before the analyst, and the release blocks on it at the handoff. Asked of the
    stretches that count — a stretch whose audio was replaced names a recording no part is any
    more — so a part leaves the question by being recorded over and by nothing else.
    """
    return sorted({stretch.take_id for stretch in stretches})


def untold_parts(parts: list[IRTake], rehearsal_take_ids: list[str]) -> list[IRTake]:
    """Which of the rehearsal's current parts carry nobody's words, in the order they read.

    Empty is told. A part the team recorded again arrives with no stretch of its own, and the
    stretches of the recording it replaced went with that recording (ADR 0023) — so a part can
    stand in the **Packet** as the rehearsal while nothing anybody said is about it.

    Asked of the parts and answered about the parts, because the question is which recording is
    current and that is a fact of the takes. What was heard of it is a fact of the report, and
    the function below is where that is asked (ADR 0026).
    """
    return [part for part in parts if part.id not in rehearsal_take_ids]


def unheard_parts(state: BackTranslationState, rehearsal_take_ids: list[str]) -> list[str]:
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


def _landed_without_a_frase(raw: str, session: str) -> None:
    """A missing element the analyst named no readable frase for, counted rather than guessed.

    It is the one silent landing in this parser: an unrecognised `where` is refused out loud
    above, and a `where` left off lands on the frase the reply did name, which is the rule and
    not an accident (ADR 0007). A chunk left off degrades to no address at all — the team is
    sent to record more and go back to the rehearsal — and nothing said so, so neither the
    golden scripts nor production could say how often the model leaves it out. Her prompt item
    leaves the number optional while our output block requires it, and the item is not ours to
    edit, so this counts until she rules.

    The reply is behind it whole, as every other line in this file carries one.
    """
    logger.warning("BT analyst missing finding without a chunk for session %s: %s", session, raw)


def _dropped_without_a_frase(kind: FindingKind, note: str, raw: str, session: str) -> None:
    """An addition or an unclear the analyst named no readable frase for; dropped, not raised.

    A missing element still lands with no chunk at all — the story simply has not been told
    that far, and `_landed_without_a_frase` counts it. The other two kinds are a statement
    about a chunk, and one naming none, or one outside the reading the analyst was given,
    names nothing the team can act on: it goes the way the retired evidence kind does,
    dropped and the rest of the reply read, rather than reaching the tablet as a finding
    with no stretch.

    Said only once the reading has been accepted, the way `_dropped` is: a reply that drops
    every one of its findings to this rule is refused instead (`_parse_analysis`), and
    announcing a drop it then threw away whole would send the next investigation to the
    wrong place.

    The reply is behind it whole, as every other line in this file carries one.
    """
    logger.warning(
        "BT reply named %s with no readable frase (note: %s); dropped it and read the rest "
        "for session %s: %s",
        kind.value,
        note,
        session,
        raw,
    )


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

    An addition or an unclear naming no chunk this reading has, or one outside it, is
    dropped the same way (ENG-1145) — but a reply left with nothing at all once every one of
    its findings dropped for that reason is not a clean reading: it is refused like a
    malformed reply, through the same `_refused` this function already returns None from,
    because a reply that named findings and lost every one of them to an unreadable frase is
    the ENG-719 failure again — a good telling-back blessed on the strength of a reply that
    said nothing usable.
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
    considered = [
        one for one in reported if not _is_the_retired_evidence_kind(one) and not _is_a_nuance(one)
    ]

    findings: list[Finding] = []
    dropped_without_a_frase: list[tuple[FindingKind, str]] = []
    for entry in considered:
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
        frase = entry.get("frase", entry.get("chunk"))
        chunk = _chunk_named(frase, segments)
        if chunk is None and kind is not FindingKind.MISSING:
            dropped_without_a_frase.append((kind, note))
            continue
        lands_on = _segment_pointed_at(
            frase,
            segments,
            kind=kind,
            where=entry.get("where", "after" if "frase" in entry else None),
            raw_reply=raw,
            session=session,
        )
        if kind is FindingKind.MISSING and chunk is None:
            _landed_without_a_frase(raw, session)
        findings.append(
            Finding.model_validate(
                {
                    "kind": wire_name,
                    "note": note[:1000],
                    "chunk": chunk,
                    "segment_id": lands_on,
                }
            )
        )

    if considered and not findings:
        _refused("every finding named no readable frase", raw, session)
        return None

    for kind, note in dropped_without_a_frase:
        _dropped_without_a_frase(kind, note, raw, session)
    _dropped(reported, raw, f"session {session}")
    nuances = [_a_nuance(one, segments) for one in reported if _is_a_nuance(one)]
    return BtAnalysis(findings=findings, nuances=[one for one in nuances if one is not None])


def _words_of(text: str) -> str:
    return re.sub(r"[\W_]+", " ", unicodedata.normalize("NFC", text).lower()).strip()


def _stands_in(quote: str, transcript: str | None) -> bool:
    words = _words_of(quote)
    return bool(words) and f" {words} " in f" {_words_of(transcript or '')} "


def _a_nuance(entry: dict[str, Any], segments: list[IRSegment]) -> Nuance | None:
    chunk = _chunk_named(entry.get("frase"), segments)
    quote = str(entry.get("quote", "")).strip()
    story = str(entry.get("story", "")).strip()
    if chunk is None or not story or not _stands_in(quote, segments[chunk - 1].transcript):
        return None
    return Nuance(
        note=str(entry.get("note", "")).strip() or f"«{quote}» — {story}",
        chunk=chunk,
        segment_id=segments[chunk - 1].id,
        quote=quote,
        story=story,
    )


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

    Only an int or a numeral string is read; a float such as `2.0` is neither and names no
    position, whole-valued or not — the contract asks for an int, and a reply answering with
    a float is not naming a frase the parser accepts.
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
        MEANING_MAP=validator_map_block(pericope_num, load_map(pericope_num).book),
        SEGMENTS=segments_block(segments, language_code),
    )
    try:
        raw = await room_agent().analyst.call_agent(
            role="analyst",
            system_prompt=system,
            user_content="Analyze the telling-back now. Return only the JSON object.",
            ladder=analysis_ladder(cfg),
            max_output_tokens=2500,
            effort=None,
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


def findings_after_a_part_is_recorded_again(
    findings: list[Finding], retired_segment_ids: set[str]
) -> list[Finding]:
    """The findings that survive a **Part** being recorded again, in the order they were read.

    A finding about a stretch the team has just recorded over is about audio nobody will hear
    again: it names a frase of a reading that no longer exists, and left standing it would be
    raised against a telling the team never made.

    **A Swap leaves whole.** Its two halves are joined by the frase the analyst numbered, and a
    missing element placed *after* that frase resolves to the *next* stretch — which is a slice
    of the next part. Dropping only the half that sits on the part recorded again would leave
    the other on its own, and the team would meet it the round after as a thing of its own.

    A finding pointing at no stretch is untouched, because no part can take away what names
    none: a **Missing without an address** says the team has not recorded something at all,
    which one part recorded again neither answers nor makes untrue. It is never half of a swap
    either — both halves must point at a stretch (ADR 0018) — so the rule above never reaches
    for it.

    Filtered rather than rebuilt, so what is left keeps the analyst's own order: `state.findings`
    is what the packet, the resume and the correction check all read, and the **Priority** is
    taken at the pick and never at storage.
    """
    leaving = {
        at for at, finding in enumerate(findings) if finding.segment_id in retired_segment_ids
    }
    for addition, missing in _swaps(findings):
        if addition in leaving or missing in leaving:
            leaving |= {addition, missing}
    return [finding for at, finding in enumerate(findings) if at not in leaving]


def findings_on_stretches_that_count(
    findings: list[Finding], counting: Iterable[str]
) -> list[Finding]:
    """What is left of the findings once whatever stopped counting takes its Swap with it.

    A correction replaces a stretch and a part recorded again abandons one, and a finding still
    addressed to either sends the team to a row that is no longer on their screen. The rule is
    the one a part recorded again already follows, so the two cannot drift apart.
    """
    standing = set(counting)
    gone = {
        one.segment_id
        for one in findings
        if one.segment_id is not None and one.segment_id not in standing
    }
    return findings_after_a_part_is_recorded_again(findings, gone)


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


def findings_block(findings: list[Finding] | list[Nuance], addresses: Addresses) -> str:
    return json.dumps(
        [_for_her_speaker(one, addresses) for one in findings], ensure_ascii=False, indent=2
    )


def _for_her_speaker(finding: Finding | Nuance, addresses: Addresses) -> dict[str, Any]:
    if isinstance(finding, Nuance):
        handed: dict[str, Any] = {
            "kind": "nuance",
            "note": finding.note,
            "frase": finding.chunk,
            "quote": finding.quote,
            "story": finding.story,
        }
    else:
        handed = {"kind": finding.kind.value, "note": finding.note}
        if finding.chunk is not None:
            handed["frase"] = finding.chunk
    part = addresses.part_of(finding.segment_id)
    if part and (isinstance(finding, Nuance) or finding.kind is not FindingKind.MISSING):
        handed["part"] = part
    handed["repair"] = "part"
    return handed


def points_at_a_stretch(finding: Finding | None) -> bool:
    """Whether this finding puts one stretch on screen, with a microphone to speak it again.

    The deciding fact is not whether the finding has an address — it is whether a boundary
    question was asked. `unclear` names a stretch and still asks only for that piece again,
    and the screen exists to answer *"is it in your recording, or did it come in with the
    telling?"*. Where that question is not put, there is no choice to hand over.
    """
    return (
        finding is not None
        and finding.segment_id is not None
        and finding.kind not in EVIDENCE_LIMIT_KINDS
    )
