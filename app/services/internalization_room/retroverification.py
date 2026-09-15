"""The record of everything the check learned about one session, for a person.

The **Packet** is the team's working material and travels to Refine; this is the other
artifact, written for the facilitator and the consultant, and it is the only place the
**Analyst**'s own words live. Nothing here is composed: every fact is a row the room already
wrote, read once and arranged into the document a person reads.

Two walks over the same rows answer the two questions about history, and neither costs a
query per hop. A stretch's earlier tellings are found by walking *backwards* over a map from
a successor to the row it replaced; a **Hard stretch** mark, which names the first telling of
a chain and is cleared by nothing, is placed on the stretch standing now by walking the same
chain *forwards*. A chain that reaches no stretch standing was abandoned rather than replaced
(ADR 0004): its rows are listed apart, and a mark on it names no stretch at all.

It is refused to nobody and composed for every state. A session the analyst never read, one
nobody approved, one whose reading moved after the approval — each is a thing the consultant
has to be able to see, and an empty file that reads like a clean one is the failure this
exists to prevent. What each state means is said in a sentence in her own language, beside
the flag a program reads.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRRelease, IRSegment, IRSession, IRTake
from app.models.internalization_room import (
    RetroverificationAttempt,
    RetroverificationFile,
    RetroverificationFinding,
    RetroverificationHardStretch,
    RetroverificationListening,
    RetroverificationRelease,
    RetroverificationStretch,
    RetroverificationTake,
    RetroverificationTelling,
)
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Finding,
    rehearsed_parts,
    unheard_parts,
)
from app.services.internalization_room.hard_stretches import hard_stretches_of
from app.services.internalization_room.release import releases_of_passage
from app.services.internalization_room.segments import (
    current_segments,
    final_segments,
    retired_segments,
    told_back,
)
from app.services.internalization_room.sessions import back_translation_of
from app.services.internalization_room.takes import takes_of

#: Where a facilitator's browser fetches one take, as the file points at it. A path and never
#: a signed link: a signed URL expires in minutes and this document is meant to outlive it.
TAKE_AUDIO_ROUTE = "/api/internalization-room/facilitator/takes/{take_id}/audio"

#: The three things the file has to say in words, in the language the room speaks to the
#: consultant. Each stands beside a flag, and neither replaces the other: the flag is what a
#: program reads, and the sentence is what tells a person what a missing number means.
DRAFT_NOT_APPROVED = (
    "Este rascunho não foi aprovado: a numeração das frases é a da leitura de agora"
)
READING_MOVED = "A leitura mudou desde a versão {version}: frases sem número não estavam nela"
NEVER_ANALYSED = "O analista nunca leu esta tradução: não houve conferência"


def _moment(when: datetime | None) -> str | None:
    return when.isoformat() if when else None


def _finding_view(finding: Finding) -> RetroverificationFinding:
    return RetroverificationFinding(
        kind=finding.kind.value,
        note=finding.note,
        segment_id=finding.segment_id,
        chunk=finding.chunk,
        fills_silence=finding.fills_silence,
        raised_by_check=finding.raised_by_check,
    )


def _telling_view(row: IRSegment) -> RetroverificationTelling:
    return RetroverificationTelling(
        segment_id=row.id,
        transcript=row.transcript,
        pass_number=row.pass_number,
        tellings=row.tellings,
        bridge_take_id=row.bridge_take_id,
        created_at=_moment(row.created_at),
        superseded_at=_moment(row.superseded_at),
    )


def _release_view(release: IRRelease) -> RetroverificationRelease:
    return RetroverificationRelease(
        version=release.version,
        session_id=release.session_id,
        approved_at=release.approved_at.isoformat(),
        device_id=release.device_id,
        forced_by=release.forced_by,
        forced_at=_moment(release.forced_at),
        forced_open_findings=release.forced_open_findings or [],
        package_sha256=release.package_sha256,
    )


def _take_view(take: IRTake) -> RetroverificationTake:
    return RetroverificationTake(
        take_id=take.id,
        kind=take.kind.value,
        scope=take.scope,
        ordinal=take.ordinal,
        pass_number=take.pass_number,
        sha256=take.sha256,
        recorded_at=_moment(take.created_at),
        url=TAKE_AUDIO_ROUTE.format(take_id=take.id),
    )


def _frozen_numbers(latest: IRRelease | None) -> dict[str, int] | None:
    """The frase each stretch was given by the latest **Version**, or nothing when there is none.

    Read out of the stored packet rather than recomputed from the rows, which is the whole
    point of freezing it: every reading renumbers, and a comment filed against frase 3 has to
    go on meaning the stretch it meant.
    """
    if latest is None:
        return None
    frozen = latest.packet.get("back_translation", {}).get("segments", [])
    return {
        entry["segment_id"]: entry["frase"]
        for entry in frozen
        if entry.get("segment_id") and entry.get("frase") is not None
    }


def _walked_forward(
    start: str, replaced_by: dict[str, str | None], standing: set[str]
) -> str | None:
    """Where a chain of replacements ends, or nothing when it ends nowhere.

    `replaced_by` names only the rows that stopped counting, so a row absent from it is one
    still standing. A row present with no successor was abandoned, and there is nothing at the
    end of that chain to point at.

    `standing` is every row that still counts and not only the leaves. A stretch the team
    divided is standing and is not a leaf, so a chain ending on one ends somewhere: read off
    the leaves, those rows came back as abandoned and the file told the consultant the team had
    thrown the recording away when what they did was hear two ideas in it.
    """
    at: str | None = start
    seen: set[str] = set()
    while at is not None and at in replaced_by and at not in seen:
        seen.add(at)
        at = replaced_by[at]
    return at if at is not None and at in standing else None


def _history_of(
    stretch: IRSegment, replaces: dict[str, IRSegment]
) -> list[RetroverificationTelling]:
    """Every earlier telling of this stretch, oldest first.

    Walked backwards over rows already in hand: the chain the rows carry runs forward, so the
    map is built once from a successor to the row it replaced rather than asked of the
    database one hop at a time.
    """
    walked: list[IRSegment] = []
    seen: set[str] = set()
    at = replaces.get(stretch.id)
    while at is not None and at.id not in seen:
        seen.add(at.id)
        walked.append(at)
        at = replaces.get(at.id)
    return [_telling_view(row) for row in reversed(walked)]


def _listening(
    telling_back: BackTranslationState, parts: list[str]
) -> list[RetroverificationListening]:
    """The report part by part, with the parts nobody heard named as such.

    Asked of the parts the stretches standing now are slices of, which is the subject both the
    check and the release ask about: a part leaves the question by being recorded over and by
    nothing else.
    """
    unheard = set(unheard_parts(telling_back, parts))
    reported = {entry.take_id: entry for entry in telling_back.played_by_take}
    listened = []
    for take_id in parts:
        entry = reported.get(take_id)
        listened.append(
            RetroverificationListening(
                take_id=take_id,
                played_ranges=list(entry.played_ranges) if entry else [],
                clip_duration_ms=entry.clip_duration_ms if entry else 0,
                heard=take_id not in unheard,
            )
        )
    return listened


def _notices(*, latest: IRRelease | None, reading_moved: bool, never_analysed: bool) -> list[str]:
    said = []
    if latest is None:
        said.append(DRAFT_NOT_APPROVED)
    elif reading_moved:
        said.append(READING_MOVED.format(version=latest.version))
    if never_analysed:
        said.append(NEVER_ANALYSED)
    return said


async def retroverification_file(db: AsyncSession, session: IRSession) -> RetroverificationFile:
    """The whole record of one session's check, assembled from the rows the room wrote.

    The releases are the passage's and not the session's, because that is the scope a
    **Version** is per: a draft another conversation about this passage approved is a draft of
    this passage, and a list scoped to one session would hide it from the person reading the
    history. A session naming no project has none, which is the same answer the approval gives.

    The numbering is the session's own. A **Version** freezes the reading of the session it was
    built from, so the numbers come from the last release *this* session wrote and never from
    whatever the passage was approved as afterwards: read off the passage's last version, a
    file came back with every number gone and a line saying the reading had moved, about a
    reading that had not moved. The list beside it stays the passage's, each row naming the
    conversation that wrote it.

    Every stretch standing is listed, told back or not. One whose mother tongue was just
    recorded again carries nothing the team said — and dropping it dropped the telling before
    it with it, which is the one thing a consultant opens this document for. It has no `frase`:
    a live reading is numbered by the enumeration the analyst was given, and a stretch with
    nothing said on it was not in that.

    `superseded_attempts` keeps the listening each attempt reported and its findings with their
    notes; `abandoned` keeps the rows of a chain nothing took over. Neither is inside a
    stretch's history, because neither is history *of* anything standing now.
    """
    telling_back = back_translation_of(session)
    stretches = await final_segments(db, session.id)
    counting = await current_segments(db, session.id)
    retired = await retired_segments(db, session.id)
    takes = await takes_of(db, session.id)
    releases = (
        await releases_of_passage(db, session.project_id, session.pericope)
        if session.project_id
        else []
    )
    marks = (await hard_stretches_of(db, [session.id])).get(session.id, [])

    minted_here = [release for release in releases if release.session_id == session.id]
    latest = minted_here[-1] if minted_here else None
    frozen = _frozen_numbers(latest)
    told = told_back(stretches)
    live = {stretch.id: position for position, stretch in enumerate(told, start=1)}
    standing = {stretch.id for stretch in counting}
    replaced_by = {row.id: row.superseded_by_id for row in retired}
    replaces = {row.superseded_by_id: row for row in retired if row.superseded_by_id}

    numbered = []
    for stretch in stretches:
        numbered.append(
            RetroverificationStretch(
                segment_id=stretch.id,
                frase=frozen.get(stretch.id) if frozen is not None else live.get(stretch.id),
                take_id=stretch.take_id,
                starts_ms=stretch.starts_ms,
                ends_ms=stretch.ends_ms,
                pass_number=stretch.pass_number,
                tellings=stretch.tellings,
                transcript=stretch.transcript,
                parent_segment_id=stretch.parent_id,
                history=_history_of(stretch, replaces),
            )
        )

    return RetroverificationFile(
        session_id=session.id,
        pericope=session.pericope,
        project_id=session.project_id,
        generated_at=datetime.now(UTC).isoformat(),
        releases=[_release_view(release) for release in releases],
        numbering="frozen" if latest is not None else "live",
        notices=_notices(
            latest=latest,
            reading_moved=any(one.frase is None for one in numbered),
            never_analysed=telling_back.never_analysed,
        ),
        approved=latest is not None,
        analysed=not telling_back.never_analysed,
        checked=telling_back.checked,
        checked_at=_moment(telling_back.checked_at),
        stretches=numbered,
        abandoned=[
            _telling_view(row)
            for row in retired
            if _walked_forward(row.id, replaced_by, standing) is None
        ],
        findings=[_finding_view(finding) for finding in telling_back.findings],
        superseded_attempts=[
            RetroverificationAttempt(
                findings=[_finding_view(finding) for finding in attempt.findings],
                played_by_take=list(attempt.played_by_take),
            )
            for attempt in telling_back.superseded
        ],
        listening=_listening(telling_back, rehearsed_parts(stretches)),
        hard_stretches=[
            RetroverificationHardStretch(
                segment_id=_walked_forward(mark.segment_id, replaced_by, standing),
                first_telling_id=mark.segment_id,
                tellings=mark.tellings,
                crossed_at=mark.crossed_at.isoformat(),
            )
            for mark in marks
        ],
        takes=[_take_view(take) for take in takes],
    )
