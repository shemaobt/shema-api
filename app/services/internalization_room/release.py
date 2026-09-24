"""The handoff artifact a finished internalization session sends to OBT Refine.

The artifact carries not just the audio, but the history of how the team reached it and
which limits still need people who understand the mother tongue: the bridge mode, the
scenes practiced, the semantic evidence events and their open points, the telling-back
with its findings and playback report, and every superseded attempt clearly marked.

The release fails closed. A blocker means the session is not ready to travel — never a
partial artifact — because a package missing the coverage floor, the rehearsal audio, the
telling-back, the analyst's reading of it, a stretch nobody told back or a recording nobody
told back would look downstream exactly like a finished one; so would one composed for a
panorama, which is not a draft of a passage at all. Those seven are missing material, and
nothing overrules them: there is nothing in a rehearsal nobody recorded for anybody to
overrule.

The other two are Marcia's gate — an open finding the telling-back still carries, and a part
of the rehearsal the team never heard through — and they are a dispute rather than a hole.
A person can look at either and disagree, and only a facilitator's own code opens that door
(ADR 0019). The output is always labeled ``first_team_rehearsal`` / ``ready_for_refine``:
the system never claims to have understood or approved the mother-tongue recording itself.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ReleaseWithoutProject
from app.db.models.internalization_room import (
    IRQuestion,
    IRRelease,
    IRSegment,
    IRSession,
    IRTake,
    IRTakeKind,
)
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Finding,
    SupersededAttempt,
    findings_remaining,
    rehearsed_parts,
    unheard_parts,
    untold_parts,
)
from app.services.internalization_room.canon.book_material import vendor_pin
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.comprehension.checkpoints import (
    checkpoints_for,
    scene_ids_for,
)
from app.services.internalization_room.comprehension.session_readiness import (
    evaluate_session_comprehension,
)
from app.services.internalization_room.coverage import floor_met
from app.services.internalization_room.segments import (
    divided_segments,
    final_segments,
    retired_segments,
    told_back,
)
from app.services.internalization_room.sessions import (
    back_translation_of,
    comprehension_of,
    is_panorama,
)
from app.services.internalization_room.takes import current_parts, takes_of

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
SCHEMA_VERSION = "tripod.internalization-release.v0.6"

#: The whole of what a facilitator's code can set aside, and the one place that says so. They
#: are Marcia's gate — no open finding, and the whole rehearsal heard — and they are the only
#: two a person can disagree about after looking at them. Every other blocker is missing
#: material: there is nothing in a rehearsal nobody recorded for anybody to overrule.
FORCEABLE_BLOCKERS = frozenset({"telling_back_not_checked", "playback_did_not_cover_the_clip"})

#: The three the tablet has a door for and the team's own route names ground on: an untold
#: part by its take, an unheard part by its take, an untold stretch by its own id (ADR 0027,
#: ADR 0028). One name for the set so the strings live once rather than at every site that
#: asks whether a blocker carries ground.
GROUNDED_BLOCKERS = frozenset({"untold_part", "playback_did_not_cover_the_clip", "untold_stretch"})

#: Where the facilitator and the consultant read everything the check learned about a session.
#: The route is a later slice's; the packet says where it will be so the two land together.
RETRO_ROUTE = "/api/internalization-room/facilitator/sessions/{session_id}/retroverificacao"


class InternalizationReleaseBlocked(ConflictError):
    def __init__(self, blockers: list[str]) -> None:
        self.blockers = blockers
        super().__init__("internalization release blocked: " + ", ".join(blockers))


def _package_sha256(artifact: dict[str, Any]) -> str:
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
        **attempt.model_dump(mode="json", exclude={"findings"}),
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
        "recorded_at": take.created_at.isoformat() if take.created_at else None,
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


def _check_block(
    telling_back: BackTranslationState,
    told: list[IRSegment],
    session_id: str,
    *,
    heard_complete: bool,
    version: int | None,
    forced: bool,
) -> dict[str, Any]:
    """What the check of this session amounts to, in her names and with none of the analyst's.

    ``version`` and ``forced`` are facts of the release row, which is written after the packet
    is built, so they are the caller's to hand in: null and false on the live read, the row's
    own on the approval (ADR 0020).

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

    The note never enters. What is open is a kind and an address; why it is open is the
    consultant's material and travels in the retroverification file.
    """
    frase_of = {stretch.id: frase for frase, stretch in enumerate(told, start=1)}
    take_of = {stretch.id: stretch.take_id for stretch in told}
    findings: list[dict[str, Any]] = []
    for finding in telling_back.findings:
        entry: dict[str, Any] = {
            "kind": finding.kind.value,
            "idx": finding.segment_id,
            "clipKey": take_of.get(finding.segment_id) if finding.segment_id else None,
        }
        if finding.segment_id in frase_of:
            entry["frase"] = frase_of[finding.segment_id]
        findings.append(entry)
    return {
        "version": version,
        "status": _check_status(telling_back.checked, forced),
        "conferida": telling_back.checked,
        "forced": forced,
        "heardComplete": heard_complete,
        "lastCheckAt": telling_back.checked_at.isoformat() if telling_back.checked_at else None,
        "findings": findings,
        "retroUrl": RETRO_ROUTE.format(session_id=session_id),
    }


def _judge(blockers: list[str], waived: frozenset[str]) -> None:
    """Refuse over whatever the waiver did not name, and say nothing otherwise.

    One sentence in one place because two callers ask it: the build, whose whole job after
    composing is this, and the approval, which has to compare the packet before it gets
    here. A waiver filters the refusal and never the packet.
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

    It is a name anyone may say. `build_internalization_release` used to take a set of
    blockers to waive, which no caller in the application ever passed: what wanted it was a
    reader that had already decided the gate was not its subject, and that reader is asking
    for the composition and not for a softer judgement. Answering with the two apart says so,
    and it is the only door onto a blocked session's live packet — the Desk's own route
    rebuilds under the whole list and refuses.

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
    is refused unless every part the stretches name was played through, each in its own
    milliseconds.

    Only whether anything is unheard is read here. Which parts they are is the same answer, and
    it is what the room says to the team when it sends them back; this decides one thing.

    What the report has to name is asked of the stretches, which say which recording each is a
    slice of and were checked on the way in. Not of the takes table: ``created_at`` there is
    when the upload landed, the tablet's outbox drains whenever the link comes back, and the
    newest-arriving rehearsal is sometimes the one the team abandoned.

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
    word for the state, the one ``FailSafe.UNTOLD_STRETCH`` already speaks aloud on the tablet.

    Once rather than once per stretch: a blocker is an errand, and the errand is the same one.

    ``untold_part`` is that same argument about a recording, and it is the one question here the
    stretches cannot answer. A part the team recorded again arrives carrying nobody's words and
    takes the stretches of the recording it replaced with it (ADR 0023), so nothing is left for
    the line above, for ``first_untold`` or for the listening to see, while the packet goes on
    carrying that recording as the part. Which recording is current is a fact of the takes, and
    it is asked of them here; what the team heard of it is a fact of the report, and that is why
    the listening stays derived from the stretches where ADR 0023 left it.

    It stands beside ``no_telling_back`` rather than behind it. A session that told nothing back
    has an empty reading *and* recordings nobody explained, both are true of it, and each sends
    the team somewhere else. Once rather than once per part, for the reason above.

    Both this and the listening below start from `rehearsed_parts`, the grounds the stretches
    name, and ask different things of it: whether a current part is among them at all, and
    whether the report covers the ones that are. The input is shared and the answer is not —
    deriving the listening from the takes is what ADR 0023 refused and ADR 0026 keeps refused.

    Not forceable, for the reason the stretch is not: ground nobody told back is missing material
    and not a dispute, and there is nothing in a recording nobody explained to disagree with.

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

    ``package_sha256`` is taken before ``created_at``, ``release_id``, ``version`` and
    ``check`` are written into the returned dict, so the hash covers none of the four.
    ``created_at`` records when this read happened and not what the session holds; the two
    after it say which approval this content became; ``check`` is a view of that approval's
    row, which is written later still and so is derived here with no version and no force
    (ADR 0020). All four would move without the content moving, and two reads of an unchanged
    session must carry one hash. A consumer verifying the fingerprint drops those four keys
    and hashes the rest.
    """
    blockers: list[str] = []
    if is_panorama(session.pericope):
        raise InternalizationReleaseBlocked(["panorama_sessions_never_release"])

    comprehension = comprehension_of(session)
    telling_back = back_translation_of(session)
    checkpoints = list(checkpoints_for(session.pericope))
    scene_ids = scene_ids_for(session.pericope)
    readiness = evaluate_session_comprehension(
        checkpoints=checkpoints,
        scene_ids=scene_ids,
        ledger=comprehension.ledger,
        practiced_scene_ids=comprehension.practiced_scene_ids,
    )
    stretches = await final_segments(db, session.id)
    told = told_back(stretches)
    replaced = await retired_segments(db, session.id)
    divided = await divided_segments(db, session.id)
    takes = await takes_of(db, session.id)
    ensaio_takes = [take for take in takes if take.kind is IRTakeKind.ENSAIO]
    retro_takes = [take for take in takes if take.kind is IRTakeKind.RETRO]
    parts = current_parts(takes)

    if not floor_met(session.coverage_state or {}, session.pericope):
        blockers.append("coverage_floor_not_met")
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
    if untold_parts(parts, rehearsed):
        blockers.append("untold_part")
    unheard = unheard_parts(telling_back, rehearsed)
    if rehearsed and unheard:
        blockers.append("playback_did_not_cover_the_clip")

    by_id = {checkpoint.id: checkpoint for checkpoint in checkpoints}
    open_points = []
    for point in readiness.evaluation.open_points:
        checkpoint = by_id.get(point.unit_id)
        open_points.append(
            {
                "unit_id": point.unit_id,
                "reason": point.reason,
                "checkpoint_kind": checkpoint.kind if checkpoint else None,
                "scene_id": checkpoint.scene_id if checkpoint else None,
                "source_id": checkpoint.source_id if checkpoint else None,
                "canonical": checkpoint.canonical if checkpoint else None,
            }
        )

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
        "comprehension": {
            "outcome": readiness.evaluation.outcome.value,
            "supported_unit_ids": readiness.evaluation.supported_unit_ids,
            "total_units": len(checkpoints),
            "practiced_scene_ids": comprehension.practiced_scene_ids,
            "events": [event.model_dump(mode="json") for event in comprehension.ledger],
            "open_points": open_points,
        },
        "audio": {
            "recording_grain": _recording_grain(parts),
            "rehearsal_takes": [_take_view(take) for take in parts],
        },
        "back_translation": {
            "scope": telling_back.scope,
            "checked": telling_back.checked,
            "segments": [
                {**_segment_view(segment), "frase": frase}
                for frase, segment in enumerate(told, start=1)
            ],
            "findings": [_finding_view(finding) for finding in telling_back.findings],
            "played_by_take": [
                entry.model_dump(mode="json") for entry in telling_back.played_by_take
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
        "open_questions": len(open_points)
        + sum(1 for question in questions if question.status.value != "resolved")
        + findings_remaining(telling_back.findings),
    }
    artifact["package_sha256"] = _package_sha256(artifact)
    approved = await _release_of(db, session, artifact["package_sha256"])
    artifact["release_id"] = approved.id if approved else None
    artifact["version"] = approved.version if approved else None
    artifact["created_at"] = datetime.now(UTC).isoformat()
    artifact["check"] = _check_block(
        telling_back, told, session.id, heard_complete=not unheard, version=None, forced=False
    )
    return artifact, blockers


async def build_internalization_release(db: AsyncSession, session: IRSession) -> dict[str, Any]:
    """Build the closed-world release for one session, or refuse with typed blockers.

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
    ``FORCEABLE_BLOCKERS`` is the whole of what a force sets aside, and ``approve_release`` is
    where it is named, because that is where somebody decided it;
    ``panorama_sessions_never_release`` is raised by the composer before the list exists and so
    is out of reach of any of it, because a panorama is not a draft of a passage at all.

    What a forced package says is unchanged: ``checked`` false and every open finding in
    ``findings``. Judging the quality of a telling-back is not this artifact's job — carrying
    it honestly is, and the decision that it may travel anyway was a person's and is recorded
    on the release rather than dressed up here.

    This judges under the whole list and sets nothing aside. A caller that wants the packet of
    a session the gate refuses is not asking for a softer judgement: it is asking for the
    composition, and ``compose_internalization_release`` is where it says so.
    """
    artifact, blockers = await compose_internalization_release(db, session)
    _judge(blockers, frozenset())
    return artifact


async def _release_of(
    db: AsyncSession, session: IRSession, package_sha256: str
) -> IRRelease | None:
    """The release this content *is*, if this content is the approved draft of the passage.

    Literally the question the approval asks, over the same row: the last release of this
    pericope and project, kept only when its hash is the fresh one. Scoping it to the session
    instead would let the composer and the approval disagree — after another conversation
    about the same passage approved a v2, a read of the first session would still name its
    v1 while approving it would mint a v3, and the packet would name a draft that is no
    longer the one the passage is on.

    A session that names no project has no release to be: the number is per project, and a
    room on the shared key names none.
    """
    if session.project_id is None:
        return None
    latest = await _latest_release(db, session.project_id, session.pericope)
    if latest is None or latest.package_sha256 != package_sha256:
        return None
    return latest


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

    Refused before anything is composed when the session names no project, because the
    number is per project and per pericope and there is nothing to number it under. The
    blockers the packet raises are the gate, and ``forced_by`` is the one thing that moves
    it: named, the two codes of ``FORCEABLE_BLOCKERS`` are waived and the row records who
    forced it, when, and which findings were open at that moment. Everything else still
    refuses, under a force exactly as without one.

    ``device_id`` is the tablet, and only a team's approval has one. The two never arrive
    together: a force comes from the Desk, where there is a person and no device.

    A force with nothing to waive is still a force and is still recorded as one, with an
    empty list of findings. The act was the facilitator's, and a row that hid that would say
    the team approved a draft the team did not approve.

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
    finding somebody overruled. ``coverage_floor_not_met`` is the case that shows the reach:
    it is read off ``session.coverage_state``, which is outside the hashed content, so a
    session whose floor fell after its release was written still composes the same packet and
    is still answered with that release. That is the rule ADR 0014 wrote — the number says
    which content was approved, and this content was — and it is wider than the force it was
    reopened for.

    The number is one past the last, which two approvals arriving together can both read.
    The unique index is what refuses the second, and the refusal is answered rather than
    retried: the tablet asks again and the second ask returns the release the first one
    wrote, because by then the winner is what ``_latest_release`` reads.

    The check block is stamped here and nowhere else, from the row this call is writing: the
    composer could not know the version or the force, because neither exists until the number
    is allocated. Only those two and the status they derive are rewritten — the rest of the
    block is about the telling-back, which the compare-first read has already established is
    the same telling-back. The early return above writes nothing, so a packet a facilitator
    forced comes back saying so however many times the team asks again (ADR 0020).

    The house loop for this shape retries the allocation instead — ``tier_a_service`` and
    ``speaker_service`` walk the next number, ``working_time`` re-reads and answers with the
    winner. Rejected here on purpose: those allocate a number nobody is waiting on, while a
    second approval of an unchanged packet must come back with the *same* release, and a loop
    that re-allocates after losing the race would mint the version the idempotency check
    exists to prevent. Answering the caller keeps the decision in one place.
    """
    if session.project_id is None:
        raise ReleaseWithoutProject(
            "this session names no project, so a release for it cannot be numbered"
        )

    packet, blockers = await compose_internalization_release(db, session)
    latest = await _latest_release(db, session.project_id, session.pericope)
    if latest is not None and latest.package_sha256 == packet["package_sha256"]:
        return latest

    _judge(blockers, FORCEABLE_BLOCKERS if forced_by else frozenset())

    release_id = str(uuid.uuid4())
    version = latest.version + 1 if latest is not None else 1
    forced = forced_by is not None
    packet["release_id"] = release_id
    packet["version"] = version
    packet["check"]["version"] = version
    packet["check"]["forced"] = forced
    packet["check"]["status"] = _check_status(packet["check"]["conferida"], forced)
    release = IRRelease(
        id=release_id,
        session_id=session.id,
        project_id=session.project_id,
        pericope=session.pericope,
        version=version,
        package_sha256=packet["package_sha256"],
        packet=packet,
        device_id=device_id,
        forced_by=forced_by,
        forced_at=datetime.now(UTC) if forced_by else None,
        forced_open_findings=(
            [finding.model_dump(mode="json") for finding in back_translation_of(session).findings]
            if forced_by
            else None
        ),
    )
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
