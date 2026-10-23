"""The handoff artifact a finished internalization session sends to OBT Refine.

The artifact carries not just the audio, but the history of how the team reached it and
which limits still need people who understand the mother tongue: the bridge mode, the
telling-back with its findings and playback report, and every superseded attempt clearly
marked.

The release fails closed. A blocker means the session is not ready to travel — never a
partial artifact — because a package missing the rehearsal audio, the telling-back, the
analyst's reading of it or a stretch nobody told back would look downstream exactly like a
finished one; so would one composed for a panorama, which is not a draft of a passage at all.

Only a facilitator's force moves the gate, and it passes every blocker but a rehearsal nobody
recorded, naming on the release the blockers it passed (ADR 0075): there is nothing in a
rehearsal nobody recorded to send. The output is always labeled ``first_team_rehearsal`` /
``ready_for_refine``: the system never claims to have understood or approved the mother-tongue
recording itself.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CanonNotKept, ConflictError, NotFoundError
from app.db.models.internalization_room import (
    IRQuestion,
    IRRelease,
    IRSegment,
    IRSession,
    IRTake,
    IRTakeKind,
)
from app.db.models.language import Language
from app.db.models.project import Project
from app.services.device.demo_team import is_the_demo_team
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Finding,
    SupersededAttempt,
    findings_remaining,
    frase_numbers,
    listening_to_the_parts,
    nuances_said,
    rehearsed_parts,
    unheard_parts,
)
from app.services.internalization_room.canon.book_material import vendor_pin
from app.services.internalization_room.canon.kept import reading_the_canon_of
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.segments import (
    divided_segments,
    final_segments,
    retired_segments,
    set_aside_segment_ids,
    told_back,
)
from app.services.internalization_room.sessions import (
    back_translation_of,
    claim_the_version,
    is_panorama,
    refuse_if_archived,
)
from app.services.internalization_room.takes import current_parts, is_wav, part_keys, takes_of
from app.utils.stored_time import as_utc

#: Bumped from v0.1 with the telling-back's ``chunks`` array: a stretch is addressed rather
#: than counted now, so the entries carry an id and the recording they are a slice of, and the
#: key says ``segments`` because that is what they are. Bumped again to v0.3 when the
#: conversation-mode key left the payload with the mode itself: a consumer diffing the two
#: versions finds one key gone and nothing renamed. And to v0.4 with ``release_id`` and
#: ``version``: the packet says which approved draft it is, or says it is none. And to v0.5
#: with ``played_by_take`` in place of ``played_ranges`` and ``clip_duration_ms``: the report of
#: listening names the part it was played from, and the two it replaces are gone rather than
#: still there and no longer meaning what they said (ADR 0017). And to v0.6 with the analyst's
#: note gone from every finding, in ``findings`` and in the superseded attempts alike: a
#: consumer diffing the two versions finds one key gone from every finding and nothing renamed.
#: And to v0.7 with the ``comprehension`` block gone, and its open points with it from
#: ``open_questions``: the room no longer reads practice or probes (ADR 0056). And to v0.8 with
#: ``duration_ms`` on every take, and ``recorded_at`` its **Recording time** (ADR 0072). And to
#: v0.9 with ``key`` on every rehearsal take and ``scene`` on every frase (ADR 0078).
SCHEMA_VERSION = "tripod.internalization-release.v0.9"

#: What a facilitator's force never passes, and the one place that says so: every other blocker
#: yields to it, but there is nothing to send of a passage nobody recorded (ADR 0075).
UNFORCEABLE_BLOCKERS = frozenset({"no_rehearsal_audio"})

#: The two the tablet has a door for and the team's own route names ground on: an unheard part
#: by its take and an untold stretch by its own id (ADR 0028). One name for the set so the
#: strings live once rather than at every site that asks whether a blocker carries ground.
GROUNDED_BLOCKERS = frozenset({"playback_did_not_cover_the_clip", "untold_stretch"})

#: Where the facilitator and the consultant read everything the check learned about a session:
#: the retroverification read, which the packet and the manifest both point to.
RETRO_ROUTE = "/api/internalization-room/facilitator/sessions/{session_id}/retroverificacao"


class InternalizationReleaseBlocked(ConflictError):
    def __init__(self, blockers: list[str]) -> None:
        self.blockers = blockers
        super().__init__("internalization release blocked: " + ", ".join(blockers))


#: What a packet says about a rehearsal recorded entirely as WAV, and the one shape of it:
#: the tablet records 16 kHz mono PCM, and a part that is WAV by content type is read as that.
WAV_FORMAT: dict[str, Any] = {
    "container": "wav",
    "codec": "pcm_s16le",
    "sample_rate": 16000,
    "channels": 1,
}


async def _mother_tongue(db: AsyncSession, session: IRSession) -> str | None:
    """The name of the language the session's team speaks, as the platform stores it.

    Null when the session names no team or the team names no row, and never a default: the
    tablet's sessions carry no foreign keys, and a guessed language would send a team's
    recording to Refine labelled as somebody else's.
    """
    if session.project_id is None:
        return None
    return (
        await db.execute(
            select(Language.name)
            .join(Project, Project.language_id == Language.id)
            .where(Project.id == session.project_id)
        )
    ).scalar_one_or_none()


def _slug(name: str | None) -> str:
    """Marcia's slug: accents stripped, lower case, every run outside a-z0-9 one dash.

    A name that leaves nothing, such as one with no Latin letters, is ``lrl``, as in her app.
    """
    decomposed = unicodedata.normalize("NFD", name or "")
    stripped = "".join(c for c in decomposed if not "\u0300" <= c <= "\u036f")
    return re.sub(r"[^a-z0-9]+", "-", stripped.lower()).strip("-") or "lrl"


def release_name(language: str | None, pericope: str, version: int) -> str:
    """What a release is called to Refine and to Marcia's check: language, passage, draft."""
    return f"internalize-{_slug(language)}-{pericope.lower()}-v{version}"


def released_as(release: IRRelease) -> str:
    """The name a stored release goes by: its own, or its row id when stored before ADR 0048."""
    return str(release.packet.get("release_id") or release.id)


def _package_sha256(artifact: dict[str, Any]) -> str:
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


#: What a packet says beside the draft rather than about it: its name and number, when it was
#: read, the check stamped on it, whose it is, the canon it was read against and the schema it
#: was written under.
_BESIDE_THE_DRAFT = frozenset(
    {
        "schema_version",
        "canon_vendor_pin",
        "package_sha256",
        "release_id",
        "version",
        "created_at",
        "check",
        "language",
        "session_language",
        "audio_format",
    }
)

#: Read off the draft rather than part of it, so a schema can add or reshape them freely.
_DERIVED = frozenset({"key", "scene", "index", "frase", "voiced", "duration_ms"})


def _without_derived(entry: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in entry.items() if k not in _DERIVED}


def _content(packet: dict[str, Any], *, nuances: bool) -> dict[str, Any]:
    audio = packet.get("audio") or {}
    told = packet.get("back_translation") or {}
    content = {
        k: v
        for k, v in packet.items()
        if k not in _BESIDE_THE_DRAFT and k not in ("audio", "back_translation")
    }
    content["takes"] = [take.get("sha256") for take in audio.get("rehearsal_takes", [])]
    if packet.get("check") is not None:
        content["heard_complete"] = packet["check"].get("heardComplete")
    content["back_translation"] = {
        **{k: v for k, v in told.items() if k not in ("segments", "retro_takes", "played_by_take")},
        "segments": [_without_derived(frase) for frase in told.get("segments", [])],
        "retro_takes": [take.get("sha256") for take in told.get("retro_takes", [])],
    }
    if nuances:
        content["nuances"] = [_without_derived(one) for one in packet["check"]["nuances"]]
    return content


def same_draft(stored: dict[str, Any], composed: dict[str, Any]) -> bool:
    """Whether a stored release and a composed packet are one draft, whatever schema each is in.

    The draft is its own content: the takes by fingerprint and order, the stretches, the
    telling with its findings and history, the questions, the nuances, and whether every part
    was heard. Never the schema version, the canon pin, the listening's own numbers, or what is
    read off the content, so a deploy that
    adds or reshapes those, a canon re-vendored or a listen that fills a tolerated gap never
    un-approves a draft nobody changed. Both sides are read the same way on the spot, from the
    stored packet and the composed one, never through the stored ``package_sha256``, which is
    the published hash of a whole packet and moves with the schema (ADR 0078, amending 0020).

    Nuances are compared only where the stored packet recorded them: one approved before they
    reached the record says nothing about them, and a nuance moves only with a new reading,
    which only new content brings. So is all the rest: only what both sides hold is compared,
    so a key an older schema had and a newer one dropped (``comprehension``), or one it lacked
    (the check, and with it whether every part was heard), never un-approves a draft.
    """
    recorded = "nuances" in (stored.get("check") or {})
    old, new = _content(stored, nuances=recorded), _content(composed, nuances=recorded)
    return all(old[key] == new[key] for key in old.keys() & new.keys())


#: The two grains a rehearsal can reach Refine in, and the one place that says so. Closed like
#: `CheckStatus` below and for the same reason: they are wire words a consumer switches on, and
#: a third one is a conversation rather than a return statement.
RecordingGrain = Literal["parts", "whole"]


def _recording_grain(parts: list[IRTake]) -> RecordingGrain:
    """Whether the rehearsal that reached here was told whole or in parts.

    Read off the parts' own numbers, because that is the one place the answer is: the tablet
    numbers a part it recorded and sends nothing at all for the passage told in one go. Asked of
    anything else it would be a second answer to a question the numbers already settle, and the
    two would drift.
    """
    return "parts" if any(part.ordinal is not None for part in parts) else "whole"


def _segment_view(segment: IRSegment) -> dict[str, Any]:
    """One stretch, with the address a reviewer needs to go and hear it.

    ``take_id`` with ``starts_ms``/``ends_ms`` is the slice **inside that file**, never a
    position over the concatenated passage — which is what lets a stretch be told back again
    without touching the ones after it.

    Nothing moves them. The room used to rebuild the file they were all slices of when one
    stretch was recorded again, and re-point them at it together; that gesture is gone (ADR
    0025) and what a team re-records is the **Part**, so a reader of this packet resolves every
    stretch against the recording named here and needs to do nothing else.

    ``retro_take_id`` is the recording of the team explaining this stretch, read off the row
    and never looked up. Which retro take is current is a question ``retro_takes`` cannot
    answer — it keeps every one of them, including the one a retelling replaced, the one
    nobody could make out and the one that explained a stretch the team then cut in two — and
    the stretch is the only place the answer exists.
    """
    return {
        "segment_id": segment.id,
        "take_id": segment.take_id,
        "retro_take_id": segment.bridge_take_id,
        "starts_ms": segment.starts_ms,
        "ends_ms": segment.ends_ms,
        "pass_number": segment.pass_number,
        "parent_segment_id": segment.parent_id,
        "text": segment.transcript,
    }


def _finding_view(finding: Finding) -> dict[str, Any]:
    """One finding as the packet carries it: the kind and the address, and never the why.

    The note cites internal rule ids and uses words Marcia banned from the team's ears, and
    Refine is where the team works. It is moved rather than deleted: the retroverification
    file is the one artifact written for a reader allowed to see them, and a **Forced
    release** keeps its own dump of what was overruled on the row.
    """
    return finding.model_dump(mode="json", exclude={"note"})


def _attempt_view(attempt: SupersededAttempt) -> dict[str, Any]:
    """A telling-back the team replaced, its findings read through the view above.

    They are a second list of the same thing, so a note taken out of one and left in the other
    would leave the packet carrying it anyway. What the attempt reported of its own listening
    is untouched: it is the record of what that reading stood on (ADR 0017).
    """
    return {
        **attempt.model_dump(mode="json", exclude={"findings", "checks"}),
        "findings": [_finding_view(finding) for finding in attempt.findings],
    }


def _take_view(take: IRTake) -> dict[str, Any]:
    return {
        "take_id": take.id,
        "kind": take.kind.value,
        "scope": take.scope,
        "pass_number": take.pass_number,
        "ordinal": take.ordinal,
        "sha256": take.sha256,
        "size_bytes": take.size_bytes,
        "content_type": take.content_type,
        "verified": take.verified_at is not None,
        "recorded_at": as_utc(take.recorded_at).isoformat(),
        "duration_ms": take.duration_ms,
    }


#: The three words a check can be in, and the whole of them. Closed because they are Marcia's
#: and a fourth is a conversation with her rather than a value.
CheckStatus = Literal["conferida", "forcada", "sem_conferencia"]


def _check_status(conferida: bool, forced: bool) -> CheckStatus:
    """The one place the three words are chosen, for the composer and for the approval alike.

    ``conferida`` outranks the force. The status says whether the check happened and the flag
    beside it says whether a person overruled the gate, so a session checked clean over a part
    nobody heard reads ``conferida`` with ``forced`` true: calling it ``forcada`` would report
    a check that did run as one that did not.

    ``sem_conferencia`` is the rest — never analysed, or analysed and still carrying something
    open — and it is one word rather than two because Marcia's format has three.
    """
    if conferida:
        return "conferida"
    return "forcada" if forced else "sem_conferencia"


def _scene(keys: dict[str, str], take_id: str | None) -> dict[str, str]:
    return {"scene": keys[take_id]} if take_id in keys else {}


def _check_block(
    telling_back: BackTranslationState,
    told: list[IRSegment],
    session_id: str,
    *,
    keys: dict[str, str],
    heard_complete: bool,
    version: int | None,
    forced: bool,
) -> dict[str, Any]:
    """What the check of this session amounts to, in her names and with none of the analyst's.

    ``version`` and ``forced`` are facts of the release row, which is written after the packet
    is built, so they are the caller's to hand in: null and false on the live read, the row's
    own on the approval (ADR 0020). So are who forced it, when and the blockers it passed:
    null here, stamped by the approval.

    ``heardComplete`` is handed in rather than asked again: the composer asks the listening
    once and both the refusal and this read the one answer, so they cannot disagree about it.

    A finding's ``frase`` is its stretch's position in ``told`` — the enumeration this packet
    freezes into ``segments`` and the analyst was numbered off — and never ``chunk``, the
    number the analyst gave: a missing element placed after frase N resolves to the stretch
    after it (ADR 0007), so the two differ by one exactly where it matters. A finding pointing
    at a stretch this reading does not carry, which is what a division or a retelling leaves
    behind, keeps its ``idx`` and has no number to give: the key is absent rather than null,
    and ``clipKey`` is null, because both are read off the list beside it. The stretch itself
    is in ``divided_segments`` or ``superseded_segments`` with its recording named, so nothing
    is lost by not repeating it here.

    ``index`` is her whole-number name for the same frase and travels exactly where ``frase``
    does; ``scene`` is the **Part key** of the part the stretch is a slice of. Neither is stable
    across versions — a division renumbers — and ``idx`` is the key that is.

    ``nuances`` are the ones standing at this reading, in her shape: a finding's keys and
    ``voiced``, which the last check round says (``now`` when its verdict named it and the team
    heard it, ``before`` when an earlier heard one had) and which is absent when no heard verdict
    said it: one notion of said, the retroverification file's. They sit here and
    not in the hashed ``back_translation`` because ``voiced`` moves with no content moving: a
    later round turns a ``now`` into ``before``, and inside the hash that would un-approve an
    unchanged draft (ADR 0078).

    The note never enters, nor a nuance's quote or story. What is open is a kind and an
    address; why it is open is the consultant's material and travels in the retroverification
    file.
    """
    frase_of = frase_numbers(told)
    take_of = {stretch.id: stretch.take_id for stretch in told}

    def addressed(kind: str, segment_id: str | None) -> dict[str, Any]:
        take_id = take_of.get(segment_id) if segment_id else None
        entry: dict[str, Any] = {"kind": kind, "idx": segment_id, "clipKey": take_id}
        if segment_id in frase_of:
            entry["frase"] = entry["index"] = frase_of[segment_id]
        return {**entry, **_scene(keys, take_id)}

    last_round = telling_back.checks[-1] if telling_back.checks else None
    heard = last_round is not None and last_round.heard_at is not None
    voiced = {
        (one.segment_id, one.quote): one.voiced
        for one in (last_round.nuances if last_round else [])
        if one.voiced == "before" or (one.voiced == "now" and heard)
    }
    said_earlier = {(one.segment_id, one.quote) for one in nuances_said(telling_back.checks)}
    nuances = []
    for nuance in telling_back.nuances:
        entry = addressed("nuance", nuance.segment_id)
        key = (nuance.segment_id, nuance.quote)
        said = voiced.get(key) or ("before" if key in said_earlier else None)
        nuances.append({**entry, "voiced": said} if said else entry)
    return {
        "version": version,
        "status": _check_status(telling_back.checked, forced),
        "conferida": telling_back.checked,
        "forced": forced,
        "heardComplete": heard_complete,
        "forcedBy": None,
        "forcedAt": None,
        "forcedBlockers": None,
        "lastCheckAt": telling_back.checked_at.isoformat() if telling_back.checked_at else None,
        "findings": [
            addressed(finding.kind.value, finding.segment_id) for finding in telling_back.findings
        ],
        "nuances": nuances,
        "retroUrl": RETRO_ROUTE.format(session_id=session_id),
    }


def _judge(blockers: list[str], waived: frozenset[str]) -> None:
    """Refuse over whatever the waiver did not name, and say nothing otherwise.

    The gate is Marcia's, whole: "Adote o meu portão inteiro, agora: sem achado em aberto e
    com a gravação toda ouvida, senão não aprova; só o código do facilitador força."

    ``checked`` says one whole reading returned no finding (ADR 0013), so a question the team
    chose not to answer makes it false and ``telling_back_not_checked`` refuses the release.
    This module used to argue the other way at length — that carrying the questions to Refine
    was the one outcome the room existed to reach — and that argument lost on what a disputed
    finding is. It is one of three things: the map wrong, which is rare and worth having; the
    team not understanding; the recogniser erring. Only the first deserves to travel, and a
    door open to all three sends the other two downstream as a passage the room approved, to
    be heard as approved at the community's check.

    The team that disagrees has a road, and it is older than this one: the raised hand, active
    the whole session, answered by a person. If that person agrees with the team, a facilitator
    forces the release with their own code, and the force is recorded on the row.
    ``UNFORCEABLE_BLOCKERS`` is the whole of what a force never sets aside, and
    ``approve_release`` is where it is applied, because that is where somebody decided it;
    ``panorama_sessions_never_release`` is raised by the composer before the list exists and so
    is out of reach of any of it, because a panorama is not a draft of a passage at all.

    What a forced packet says is unchanged: ``checked`` false and every open finding in
    ``findings``. Judging the quality of a telling-back is not this packet's job — carrying
    it honestly is, and the decision that it may travel anyway was a person's and is recorded
    on the release rather than dressed up here.

    The approval is the one caller: it compares the packet before it gets here, and a waiver
    filters the refusal and never the packet.
    """
    standing = [code for code in blockers if code not in waived]
    if standing:
        raise InternalizationReleaseBlocked(standing)


async def compose_internalization_release(
    db: AsyncSession, session: IRSession
) -> tuple[dict[str, Any], list[str]]:
    """The packet this session composes right now, and everything standing in its way.

    Composing and judging are two acts, and separating them is what lets the approval ask
    whether the content changed before it asks whether the gate is shut. The hash never
    depended on the gate — a blocker filters the refusal and not a single key of the
    artifact — so a packet composed here is the same packet either caller would have got.

    It is a name anyone may say, and it is the only door onto a session's live packet: the
    approval judges what this composes, and no route serves it (ADR 0086).

    ``panorama_sessions_never_release`` is raised rather than listed, before anything is
    read, because a panorama is not a draft of a passage at all: there is nothing to compose
    and nothing to compare, so no caller of this ever holds one.

    ``superseded_segments`` carries the stretches that stopped counting, replaced or
    abandoned, each still naming the recording it was a slice of. They used to be copied into
    ``superseded_attempts`` as text; they are rows now, and dropping them here would quietly
    take the team's own history out of the handoff.

    ``divided_segments`` carries the same debt for the other way a stretch leaves the reading.
    A stretch the team divided is current and is not a leaf, so it fell between both lists
    above — and what they had said about the whole stretch, before they heard two ideas in it,
    left the artifact in silence. Hearing it again and finding two ideas is the team working,
    not the team erring, so what they said the first time is kept rather than the division
    being refused.

    ``frase`` is added to ``segments`` here and to neither of those two. It is a position in
    one reading rather than anything on a row — the same enumeration ``segments_block`` gives
    the analyst, over the same list — so only the list that *is* a reading has one to give. A
    superseded or a divided stretch was not in the reading the team heard, and the number an
    older reading gave it is recoverable from nothing; the key is absent there rather than
    null, so a reader asking one of them for its number meets the failure instead of a silence
    that looks like an answer.

    ``telling_back_never_analysed`` keeps its precedence over the open finding, and has to. A
    team that captured the stretches and never asked for the verdict leaves no findings at
    all, which is the same package a clean check produces — told the passage is not checked, a
    facilitator would go looking for a finding that was never raised.

    The report of playback is held to the same line, and it is why the gate names the parts of
    the rehearsal rather than only measuring one clip. Silence used to pass it — an absent
    report satisfied the coverage arithmetic the way an unread telling-back satisfied
    ``checked`` — and so did a report the team had since made untrue by recording the passage
    again. Both said the team heard themselves when nobody knows whether they did. The package
    is refused unless every current part was heard, each in its own milliseconds (ADR 0074).

    Only whether anything is unheard is read here. Which parts they are is the same answer, and
    it is what the room says to the team when it sends them back; this decides one thing.

    What the report has to name is every current part, the takes `current_parts` reads in the
    tablet's own order, as her check asks it of every current take (`bt/check/route.ts:69`). A
    part nobody told back is not refused for that; it still has to be heard.

    Sessions already in flight when this shipped carry a report with no part named, and are
    refused until the team plays their rehearsal through again. That is the correct reading of
    them: a report we cannot tie to a recording is not evidence about any recording (ADR 0017).

    A session with nothing told back is not asked. ``no_telling_back`` already says what is
    wrong there, and a second blocker about playback would only repeat it in other words.

    ``untold_stretch`` is the same argument about words instead of audio. A stretch whose mother
    tongue was just re-recorded, and each half of one the team divided, is a current unit carrying
    nothing they said — legitimate inside the room, where the tablet shows it and asks for it, and
    unreadable outside: null text does not arrive downstream as unfinished, it arrives as a team
    who stood in front of that passage and said nothing.

    Unlike the line above, it silences nothing. A re-record that was never told back and never
    played leaves the team two errands, and naming one of them would send them back a second time.

    It is its own blocker rather than a widening of the two beside it, and neither could have
    been widened honestly. ``no_telling_back`` asks whether the list is empty, and a list with a
    wordless stretch in it is not empty; ``telling_back_never_analysed`` asks whether the analyst
    ever ran, which stays true from the first verdict onwards — including after the team divides
    a stretch the analyst blessed. Both are green in exactly the state this refuses. Overloading
    either would also send the facilitator the wrong errand: told that nothing was told back
    when plainly something was, they go looking for the wrong thing. The name is the room's own
    word for the state.

    Once rather than once per stretch: a blocker is an errand, and the errand is the same one.

    The guarantee is about ``segments`` and stops there. ``superseded_segments`` and
    ``divided_segments`` are history and carry null text on purpose — a stretch the team replaced
    before telling it back is exactly a stretch they replaced before telling it back, and refusing
    a release over what a session used to look like would hold the team to a state they already
    left. A reader of those two lists is reading a record, not a claim about the passage.

    Wordless is ``transcript is None`` and nothing subtler, because that is the only shape the
    room can write — both routes that store a stretch's words refuse a transcription that is
    blank or whitespace before they get here. The rule is read off ``told_back`` rather than
    restated, so what counts as words stays one sentence in one place: the analyst is numbered
    off that same list, and the two must not drift.

    ``package_sha256`` is taken before ``created_at``, ``release_id``, ``version``, ``check``,
    ``language``, ``session_language`` and ``audio_format`` are written into the returned
    dict, so the hash covers none of the seven. ``created_at`` records when this read happened
    and not what the session holds; the two after it say which approval this content became;
    ``check`` is a view of that approval's row, which is written later still and so is derived
    here with no version and no force (ADR 0020). The last three say whose rehearsal this is
    and in what format it was recorded (ADR 0048). All seven would move without the content
    moving, and two reads of an unchanged session must carry one hash. A consumer verifying
    the fingerprint drops those seven keys and hashes the rest.
    """
    with reading_the_canon_of(session.canon_pin):
        return await _composed(db, session)


async def _standing(
    db: AsyncSession, session: IRSession, takes: list[IRTake]
) -> BackTranslationState:
    """The state but its findings and nuances on a whole that stepped aside, only stored."""
    aside = await set_aside_segment_ids(db, session.id, takes)
    state = back_translation_of(session)
    return state.model_copy(
        update={
            "findings": [f for f in state.findings if f.segment_id not in aside],
            "nuances": [n for n in state.nuances if n.segment_id not in aside],
        }
    )


async def _composed(db: AsyncSession, session: IRSession) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    if is_panorama(session.pericope):
        raise InternalizationReleaseBlocked(["panorama_sessions_never_release"])
    if await is_the_demo_team(db, session.project_id):
        raise InternalizationReleaseBlocked(["demo_team_never_releases"])

    takes = await takes_of(db, session.id)
    telling_back = await _standing(db, session, takes)
    stretches = await final_segments(db, session.id, takes)
    told = told_back(stretches)
    frases = frase_numbers(told)
    replaced = await retired_segments(db, session.id)
    divided = await divided_segments(db, session.id)
    ensaio_takes = [take for take in takes if take.kind is IRTakeKind.ENSAIO]
    retro_takes = [take for take in takes if take.kind is IRTakeKind.RETRO]
    parts = current_parts(takes)
    keys = part_keys(parts)

    if not ensaio_takes:
        blockers.append("no_rehearsal_audio")
    if not stretches:
        blockers.append("no_telling_back")
    elif telling_back.never_analysed:
        blockers.append("telling_back_never_analysed")
    elif not telling_back.checked:
        blockers.append("telling_back_not_checked")
    if told != stretches:
        blockers.append("untold_stretch")
    rehearsed = rehearsed_parts(stretches)
    unheard = unheard_parts(telling_back, parts, stretches)
    if rehearsed and unheard:
        blockers.append("playback_did_not_cover_the_clip")

    questions = (
        (
            await db.execute(
                select(IRQuestion)
                .where(IRQuestion.session_id == session.id)
                .order_by(IRQuestion.created_at)
            )
        )
        .scalars()
        .all()
    )

    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "handoff_type": "internalization_release",
        "purpose": "first_team_rehearsal",
        "readiness": "ready_for_refine",
        "session_id": session.id,
        "pericope": session.pericope,
        "book": load_map(session.pericope).book,
        "canon_vendor_pin": vendor_pin(),
        "audio": {
            "recording_grain": _recording_grain(parts),
            "rehearsal_takes": [{**_take_view(take), "key": keys[take.id]} for take in parts],
        },
        "back_translation": {
            "scope": telling_back.scope,
            "checked": telling_back.checked,
            "segments": [
                {
                    **_segment_view(segment),
                    "frase": frases[segment.id],
                    **_scene(keys, segment.take_id),
                }
                for segment in told
            ],
            "findings": [_finding_view(finding) for finding in telling_back.findings],
            "played_by_take": [
                entry.model_dump(mode="json")
                for entry in listening_to_the_parts(telling_back.played_by_take, parts, stretches)
            ],
            "superseded_attempts": [_attempt_view(attempt) for attempt in telling_back.superseded],
            "superseded_segments": [_segment_view(segment) for segment in replaced],
            "divided_segments": [_segment_view(segment) for segment in divided],
            "retro_takes": [_take_view(take) for take in retro_takes],
        },
        "raised_questions": [
            {
                "question_id": question.id,
                "status": question.status.value,
                "asked_at": question.created_at.isoformat() if question.created_at else None,
            }
            for question in questions
        ],
        "open_questions": sum(1 for question in questions if question.status.value != "resolved")
        + findings_remaining(telling_back.findings),
    }
    artifact["package_sha256"] = _package_sha256(artifact)
    check = _check_block(
        telling_back,
        told,
        session.id,
        keys=keys,
        heard_complete=not unheard,
        version=None,
        forced=False,
    )
    approved = await _release_of(db, session, {**artifact, "check": check})
    artifact["release_id"] = released_as(approved) if approved else None
    artifact["version"] = approved.version if approved else None
    artifact["created_at"] = datetime.now(UTC).isoformat()
    artifact["check"] = check
    artifact["language"] = await _mother_tongue(db, session)
    artifact["session_language"] = session.language
    artifact["audio_format"] = (
        WAV_FORMAT if parts and all(is_wav(p.content_type) for p in parts) else None
    )
    return artifact, blockers


async def _release_of(
    db: AsyncSession, session: IRSession, packet: dict[str, Any]
) -> IRRelease | None:
    """The release this content *is*, if this content is the approved draft of the passage.

    Literally the question the approval asks, over the same row: the last release of this
    pericope and project, kept only when it is the same draft (``same_draft``). Scoping it to
    the session instead would let the composer and the approval disagree — after another
    conversation about the same passage approved a v2, a read of the first session would still
    name its v1 while approving it would mint a v3, and the packet would name a draft that is no
    longer the one the passage is on.

    A session that names no project has no release to be: the number is per project.
    """
    if session.project_id is None:
        return None
    latest = await _latest_release(db, session.project_id, session.pericope)
    if latest is None or not same_draft(latest.packet, packet):
        return None
    return latest


async def approved_draft(db: AsyncSession, session: IRSession) -> IRRelease | None:
    """The release this session's draft stands approved under, or none (ADR 0071).

    Asking is never allowed to fail a read or an open. What the composer would refuse (the
    panorama, the demo team) is answered none before it runs, as is a session that names no
    team, a session a Zerar archived (its work is retired, and the passage waits for its new
    session to approve), and one whose kept canon is gone, as every other reader of it
    degrades. The packet hashes the session's id, so a release another session wrote is never
    this draft's, and the composer is not run for it: the new session after a Zerar and the
    session in the other language pay one query on every beat and no more.
    """
    if (
        session.project_id is None
        or session.archive_id is not None
        or is_panorama(session.pericope)
        or await is_the_demo_team(db, session.project_id)
    ):
        return None
    latest = await _latest_release(db, session.project_id, session.pericope)
    if latest is None or latest.session_id != session.id:
        return None
    try:
        artifact, _blockers = await compose_internalization_release(db, session)
    except CanonNotKept:
        return None
    return latest if artifact["version"] == latest.version else None


async def _latest_release(db: AsyncSession, project_id: str, pericope: str) -> IRRelease | None:
    """The last release of this passage for this team, whichever session wrote it.

    Scoped to the project and the pericope and not to the session, because that is what the
    number is per: two conversations about one passage share the sequence, and numbering each
    session on its own would hand Marcia two drafts both called v1.
    """
    result = await db.execute(
        select(IRRelease)
        .where(IRRelease.project_id == project_id, IRRelease.pericope == pericope)
        .order_by(IRRelease.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def releases_of_passage(db: AsyncSession, project_id: str, pericope: str) -> list[IRRelease]:
    """Every approved draft of this passage for this team, in the order they were numbered.

    Scoped like ``_latest_release`` and for its reason: that is what a **Version** is per, so a
    number another conversation about this passage minted is a draft of this passage too, and a
    list scoped to one session would hide it from the consultant reading the history.
    """
    result = await db.execute(
        select(IRRelease)
        .where(IRRelease.project_id == project_id, IRRelease.pericope == pericope)
        .order_by(IRRelease.version)
    )
    return list(result.scalars().all())


async def release_by_version(db: AsyncSession, session: IRSession, version: int) -> IRRelease:
    """One approved draft of this session's passage, read back under the number it was given.

    Scoped to the project and the pericope, like ``_latest_release`` and for the same reason:
    that is what a **Version** is per, so a number another conversation about this passage
    minted is this session's number too. Whose passage it is was already decided by the
    caller, which resolved the session for the facilitator asking.

    A version nobody minted is not found rather than composed. The stored packet is the
    contract (ADR 0014), and a draft built on demand to fill a number would be a different
    thing wearing that number's name.
    """
    result = await db.execute(
        select(IRRelease).where(
            IRRelease.project_id == session.project_id,
            IRRelease.pericope == session.pericope,
            IRRelease.version == version,
        )
    )
    release = result.scalar_one_or_none()
    if release is None:
        raise NotFoundError(f"Internalization room session {session.id} has no release {version}")
    return release


async def approve_release(
    db: AsyncSession,
    session: IRSession,
    *,
    device_id: str | None = None,
    forced_by: str | None = None,
) -> IRRelease:
    """The team approves this passage: one numbered row, or the one that already says it.

    The session names a project: the number is per project and per pericope, and both doors
    that reach here — the team's and the facilitator's force — refuse a session that names
    none as not found before calling. The blockers the packet raises are the gate, and
    ``forced_by`` is the one thing that moves it: named, every blocker but
    ``UNFORCEABLE_BLOCKERS`` is waived and the row and the packet's check block record who
    forced it, when, which findings were open at that moment and which blockers it passed
    (ADR 0075). ``no_rehearsal_audio`` still refuses, under a force exactly as without one.

    ``device_id`` is the tablet, and only a team's approval has one. The two never arrive
    together: a force comes from the Desk, where there is a person and no device.

    A force with nothing to waive is still a force and is still recorded as one, with empty
    lists of findings and of blockers passed. The act was the facilitator's, and a row that
    hid that would say the team approved a draft the team did not approve.

    What is open at that moment is dumped from the state the packet was composed from and not
    copied out of the packet's own list, which is what lets the two differ by the analyst's
    note. The packet carries a finding as a kind and an address because Refine is where the
    team works; this row answers a facilitator asking what was overruled, which is the
    consultant's question, so it keeps the words the analyst wrote.

    Unchanged content returns the release that already exists rather than minting a version
    beside it: a new **Version** starts with zero listeners on Marcia's external check, so
    one that means nothing changed is worse than none. "Unchanged" is measured against the
    last release of this pericope and project — a packet that comes back to an earlier
    version's content is a later draft, not that version again, and giving its number back
    would put comments on a draft nobody is looking at.

    The comparison happens before the gate is judged, which is what ADR 0019 means by ADR
    0014 holding under force: a draft a facilitator already forced is a draft that exists, so
    the team asking again about the very same content is answered with it rather than told a
    second time about a finding a person has already overruled. The gate is judged only when
    the content is not that draft — and then with nothing waived unless this caller is the
    one forcing, so compare-first never becomes a force the team can reach.

    It answers an unchanged packet with its release whatever stands, and not only over the
    finding somebody overruled. A stretch captured without words after the approval is the
    case that shows the reach: the packet carries only the stretches the team told back, so
    its hash does not move, and the team is answered with that release while
    ``untold_stretch``, which the team cannot waive, stands. That is the rule ADR 0014 wrote — the
    number says which content was approved, and this content was — and it is wider than the
    force it was reopened for.

    The number is one past the last, which two approvals arriving together can both read.
    The unique index is what refuses the second, and the refusal is answered rather than
    retried: the tablet asks again and the second ask returns the release the first one
    wrote, because by then the winner is what ``_latest_release`` reads.

    The check block is stamped here and nowhere else, from the row this call is writing: the
    composer could not know the version or the force, because neither exists until the number
    is allocated. Only those two, the status they derive and the force's who, when and blockers
    passed are rewritten — the rest of the block is about the telling-back, which the
    compare-first read has already established is the same telling-back. The early return
    above writes nothing, so a packet a facilitator forced comes back saying so however many
    times the team asks again (ADR 0020).

    The house loop for this shape retries the allocation instead — ``tier_a_service`` and
    ``speaker_service`` walk the next number, ``working_time`` re-reads and answers with the
    winner. Rejected here on purpose: those allocate a number nobody is waiting on, while a
    second approval of an unchanged packet must come back with the *same* release, and a loop
    that re-allocates after losing the race would mint the version the idempotency check
    exists to prevent. Answering the caller keeps the decision in one place.

    No release is minted on an archived session: one a Zerar archived is answered as gone,
    and so is one a Zerar overtakes while the packet is composed, because the insert lands
    only while the session's ``version`` is still the one read here (ADR 0052, ADR 0066).
    """
    assert session.project_id is not None
    await refuse_if_archived(db, session)

    packet, blockers = await compose_internalization_release(db, session)
    latest = await _latest_release(db, session.project_id, session.pericope)
    if latest is not None and same_draft(latest.packet, packet):
        await refuse_if_archived(db, session)
        return latest

    _judge(blockers, frozenset(blockers) - UNFORCEABLE_BLOCKERS if forced_by else frozenset())
    passed = sorted(set(blockers)) if forced_by else None

    row_id = str(uuid.uuid4())
    version = latest.version + 1 if latest is not None else 1
    forced = forced_by is not None
    forced_at = datetime.now(UTC) if forced else None
    packet["release_id"] = release_name(packet["language"], session.pericope, version)
    packet["version"] = version
    packet["check"]["version"] = version
    packet["check"]["forced"] = forced
    packet["check"]["status"] = _check_status(packet["check"]["conferida"], forced)
    packet["check"]["forcedBy"] = forced_by
    packet["check"]["forcedAt"] = forced_at.isoformat() if forced_at else None
    packet["check"]["forcedBlockers"] = passed
    release = IRRelease(
        id=row_id,
        session_id=session.id,
        project_id=session.project_id,
        pericope=session.pericope,
        version=version,
        package_sha256=packet["package_sha256"],
        packet=packet,
        device_id=device_id,
        forced_by=forced_by,
        forced_at=forced_at,
        forced_blockers=passed,
        forced_open_findings=(
            [
                finding.model_dump(mode="json")
                for finding in (
                    await _standing(db, session, await takes_of(db, session.id))
                ).findings
            ]
            if forced_by
            else None
        ),
    )
    await claim_the_version(db, session)
    db.add(release)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(
            "another approval took this version while this one was being written"
        ) from exc
    await db.refresh(release)
    return release
