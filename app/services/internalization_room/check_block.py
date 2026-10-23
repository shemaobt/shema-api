"""The check block a packet carries: her three words, the findings and nuances by address.

Read off a telling-back state and the session's rows, and written onto the release a draft
stands approved under whenever that state is written, so a version's check is the one the room
holds (ADR 0020, ADR 0081).
"""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRRelease, IRSegment, IRSession, IRTake
from app.services.internalization_room.approved_draft import approved_draft
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    frase_numbers,
    nuances_said,
    unheard_parts,
)
from app.services.internalization_room.forced import was_forced
from app.services.internalization_room.segments import (
    set_aside_segment_ids,
)
from app.services.internalization_room.takes import current_parts, part_keys, takes_of

#: Where the facilitator and the consultant read everything the check learned about a session:
#: the retroverification read, which the packet and the manifest both point to.
RETRO_ROUTE = "/api/internalization-room/facilitator/sessions/{session_id}/retroverificacao"

#: The three words a check can be in, and the whole of them. Closed because they are Marcia's
#: and a fourth is a conversation with her rather than a value.
CheckStatus = Literal["conferida", "forcada", "sem_conferencia"]


def check_status(conferida: bool, forced: bool) -> CheckStatus:
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


def scene_of(keys: dict[str, str], take_id: str | None) -> dict[str, str]:
    return {"scene": keys[take_id]} if take_id in keys else {}


def check_block(
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
        return {**entry, **scene_of(keys, take_id)}

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
        "status": check_status(telling_back.checked, forced),
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


async def standing_state(
    db: AsyncSession, session_id: str, state: BackTranslationState, takes: list[IRTake]
) -> BackTranslationState:
    """The state but its findings and nuances on a whole that stepped aside, only stored."""
    aside = await set_aside_segment_ids(db, session_id, takes)
    return state.model_copy(
        update={
            "findings": [f for f in state.findings if f.segment_id not in aside],
            "nuances": [n for n in state.nuances if n.segment_id not in aside],
        }
    )


async def _its_own_stretches(db: AsyncSession, release: IRRelease) -> list[IRSegment]:
    """The stretches the version froze, in its own order, as rows."""
    ids = [
        one["segment_id"]
        for one in (release.packet.get("back_translation") or {}).get("segments", [])
    ]
    rows = {row.id: row for row in await db.scalars(select(IRSegment).where(IRSegment.id.in_(ids)))}
    return [rows[one] for one in ids if one in rows]


async def keep_the_check_on_the_standing_release(
    db: AsyncSession, session: IRSession, state: BackTranslationState
) -> None:
    """The check state a session's telling-back is written with is its standing version's.

    Only on the stretches that version carries: a finding or a nuance on a stretch told after
    it stays on the session, so the version's frase numbers and scenes keep naming its own.

    Called by the one funnel every writer of the telling-back goes through, in its transaction,
    so a verdict, a Restart, a report of listening and a reading ahead over a draft that
    stands approved land on that version's check block too, or none of them do (ADR 0081). The
    block sits outside the hash (ADR 0020), so no fingerprint moves, and who forced it, when
    and what it passed stay as the approval wrote them.
    """
    release = await approved_draft(db, session)
    if release is None:
        return
    takes = await takes_of(db, session.id)
    parts = current_parts(takes)
    own = await _its_own_stretches(db, release)
    carried = {one.id for one in own}
    standing = await standing_state(db, session.id, state, takes)
    telling_back = standing.model_copy(
        update={
            "findings": [
                one
                for one in standing.findings
                if one.segment_id is None or one.segment_id in carried
            ],
            "nuances": [one for one in standing.nuances if one.segment_id in carried],
        }
    )
    forced = was_forced(release.forced_by, release.forced_blockers)
    stored = release.packet.get("check") or {}
    live = check_block(
        telling_back,
        own,
        session.id,
        keys=part_keys(parts),
        heard_complete=not unheard_parts(telling_back, parts, own),
        version=release.version,
        forced=forced,
    )
    release.packet = {
        **release.packet,
        "check": {
            **live,
            "forcedBy": stored.get("forcedBy") if forced else None,
            "forcedAt": stored.get("forcedAt") if forced else None,
            "forcedBlockers": stored.get("forcedBlockers") if forced else None,
        },
    }
