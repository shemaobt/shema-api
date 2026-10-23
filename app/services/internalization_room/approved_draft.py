"""Whether a team's draft stands approved: ADR 0071's question, asked by doors, menu and Desk.

A draft is one session's rehearsal takes by fingerprint, in part order (ADR 0081): only a change
of takes re-opens it, as Marcia's store clears `finalizedAt` only when a clip changes, and the
telling-back, its verdict, the questions, the nuances and the listening are the approved
version's check state. The draft is the session's (ADR 0071), so another language's session or
the one after a Zerar is never it, whatever its bytes. Read off the rows and never composed, so
it costs the same whatever the telling-back holds, and nothing here reads a session's
conversation.
"""

from __future__ import annotations

from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DraftApproved
from app.db.models.internalization_room import IRRelease, IRSession, IRTake, IRTakeKind
from app.services.device.demo_team import is_the_demo_team
from app.services.internalization_room.coverage import is_panorama
from app.services.internalization_room.live import live
from app.services.internalization_room.takes import (
    READING_ORDER,
    current_parts,
    takes_of,
    the_take_already_kept,
)


def stands_on(release: IRRelease, parts: list[IRTake]) -> bool:
    """Whether these current parts are exactly the takes the release judged, digest for digest."""
    stored = (release.packet.get("audio") or {}).get("rehearsal_takes", [])
    return [take.get("sha256") for take in stored] == [part.sha256 for part in parts]


async def latest_release(db: AsyncSession, project_id: str, pericope: str) -> IRRelease | None:
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


async def approved_draft(db: AsyncSession, session: IRSession) -> IRRelease | None:
    """The release this session's draft stands approved under, or none (ADR 0071, ADR 0081).

    The passage's latest release, kept only when this session wrote it and its takes are the
    ones the session's parts stand on now, by fingerprint in order: read off the rows, never
    composed, so asking costs the same whatever the telling-back holds and never fails a read
    or an open. The takes are read off the stored packet the same way whatever schema it was
    written in, never through its ``package_sha256``. The panorama, the demo team, a session
    that names no team and one a Zerar archived (its work is retired, and the passage waits
    for its new session to approve) are answered none.
    """
    if (
        session.project_id is None
        or session.archive_id is not None
        or is_panorama(session.pericope)
        or await is_the_demo_team(db, session.project_id)
    ):
        return None
    latest = await latest_release(db, session.project_id, session.pericope)
    if latest is None or latest.session_id != session.id:
        return None
    parts = current_parts(await takes_of(db, session.id))
    return latest if stands_on(latest, parts) else None


async def refuse_to_reopen_the_approved_draft(db: AsyncSession, session: IRSession) -> None:
    """Refuse a change a door would land on a draft that stands approved (ADR 0081).

    The door asks only when the team did not arm the tap that re-opens it.
    """
    if await approved_draft(db, session) is not None:
        raise DraftApproved("This draft is approved; the team re-opens it with the armed tap")


async def refuse_a_keep_that_reopens_the_approved_draft(
    db: AsyncSession,
    session: IRSession,
    *,
    kind: IRTakeKind,
    origin: str | None,
    chunk_index: int | None,
    pass_number: int | None,
    audio: bytes,
) -> None:
    """Refuse a join, a swap or a whole take over a joined recording on an approved draft.

    A part recorded on the recording screen carries no origin and takes one tap (ADR 0081),
    and a take already kept brings nothing new, so neither is ever refused.
    """
    if kind is not IRTakeKind.ENSAIO:
        return
    joined = origin is not None or (
        chunk_index is None
        and any(part.origin for part in current_parts(await takes_of(db, session.id)))
    )
    if joined and (
        await the_take_already_kept(
            db,
            session.id,
            kind,
            audio,
            ordinal=chunk_index,
            pass_number=pass_number,
            joined=origin is not None,
        )
        is None
    ):
        await refuse_to_reopen_the_approved_draft(db, session)


async def standing_approvals(
    db: AsyncSession, project_id: str, *, among: Collection[str] | None = None
) -> set[str]:
    """The pericopes whose draft stands approved under the team's latest live release (ADR 0081).

    A release stays in the history after a re-open, so having one is not being approved. The
    question ``approved_draft`` asks one session at a time is asked here for the whole team in
    three statements, whatever the number of released passages. ``among`` narrows the answer to
    the passages a caller already knows have a release, and an empty one asks nothing.
    """
    if among is not None and not among:
        return set()
    if await is_the_demo_team(db, project_id):
        return set()
    query = (
        select(IRRelease)
        .where(IRRelease.project_id == project_id, live(IRRelease))
        .order_by(IRRelease.version.desc())
    )
    if among is not None:
        query = query.where(IRRelease.pericope.in_(list(among)))
    latest: dict[str, IRRelease] = {}
    for release in await db.scalars(query):
        latest.setdefault(release.pericope, release)
    if not latest:
        return set()
    takes: dict[str, list[IRTake]] = {release.session_id: [] for release in latest.values()}
    for take in await db.scalars(
        select(IRTake).where(IRTake.session_id.in_(list(takes))).order_by(*READING_ORDER)
    ):
        takes[take.session_id].append(take)
    return {
        pericope
        for pericope, release in latest.items()
        if stands_on(release, current_parts(takes[release.session_id]))
    }
