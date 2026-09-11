"""The record read — one project, whole, as the ficha's ten tabs need it.

``get_project`` is the scoped row and stays exactly that. This is the screen built on it: the
row, plus the five collections that do not live on it, plus the day's derivations.

**Five reads and not one join**, which is BE-05's finding on the collection and holds here for
a narrower reason: the five children are five one-to-many relations, so a single joined
statement returns their cross product — five needs and four photos on one project is twenty
rows to regroup in Python — and every one of them is keyed on an id that came out of the
scoped read, so none can reach a project the caller cannot. The property ``_scope.py`` states
as *there is no unscoped query to call* holds here by there being no id to query with.

**This file names no guarded column.** The record is a *coordination* surface and carries the
true place (FE-44 §9.0), so there is nothing to redact — but the three authorization columns
behind every ``authorization`` key are still read by their one owner:
``_media_sharing.recorded_decision`` builds the shape and hands it over, and
``tests/test_shema/test_privacy_owners.py`` is what keeps that true of the next file too.

**The write path re-reads through here.** FE-44 §9.3 requires the response to carry *the
recomputed record, including the new progressHistory entry*, because the record screen renders
what the save actually wrote — so the create, the patch and the read answer one shape built by
one function, and a field that appears on the read cannot be missing from the save's reply.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaMediaKind
from app.db.models.shema_health import ShemaHealthAssessment
from app.db.models.shema_media import ShemaMaterial, ShemaMediaItem
from app.db.models.shema_need import ShemaNeed
from app.db.models.shema_progress import ShemaProgressEntry
from app.models.shema_projects import ShemaProjectDerived
from app.models.shema_record import (
    ShemaHealthAssessmentEntry,
    ShemaMediaPhoto,
    ShemaNeedItem,
    ShemaProgressHistoryEntry,
    ShemaProjectMaterial,
    ShemaProjectRecord,
    ShemaProjectVideo,
)
from app.services.shema._audit import ChangesSince, changes_since
from app.services.shema._media_sharing import recorded_decision
from app.services.shema._scope import RegionScope
from app.services.shema.get_project import get_project
from app.utils.shema_derivations import derive


async def _needs(db: AsyncSession, project_id: str) -> list[ShemaNeedItem]:
    """Every need on the record, oldest first — the order the tab lists them in.

    Ordered by ``submitted_at`` with ``created_at`` underneath it, because 127 export records
    carry no needs at all and a need typed in the product has no ``submittedAt`` until somebody
    fills one: an order that reads only the nullable column would shuffle the undated ones
    between requests.
    """
    stmt = (
        select(ShemaNeed)
        .where(ShemaNeed.project_id == project_id)
        .order_by(ShemaNeed.submitted_at, ShemaNeed.created_at, ShemaNeed.id)
    )
    return [ShemaNeedItem.model_validate(row) for row in (await db.execute(stmt)).scalars()]


async def _materials(db: AsyncSession, project_id: str) -> list[ShemaProjectMaterial]:
    """The project's artifacts, with the decision about sharing each one.

    Addressed by ``id`` and never by position (FE-44 §5.2), so the order is a display choice
    and not part of the contract.
    """
    stmt = (
        select(ShemaMaterial)
        .where(ShemaMaterial.project_id == project_id)
        .order_by(ShemaMaterial.created_at, ShemaMaterial.id)
    )
    return [
        ShemaProjectMaterial.model_validate(row).model_copy(
            update={"authorization": recorded_decision(row)}
        )
        for row in (await db.execute(stmt)).scalars()
    ]


async def _media(
    db: AsyncSession, project_id: str
) -> tuple[list[ShemaMediaPhoto], list[ShemaProjectVideo]]:
    """The photos and the videos, from the one table that holds both.

    One read and two lists: ``ShemaMediaItem`` is one table because the two shapes differ in one
    field each and share the whole authorization triple, which is the part every output path
    has to consult (``app/db/models/shema_media.py``). Splitting them here is a display
    concern and costs nothing.
    """
    stmt = (
        select(ShemaMediaItem)
        .where(ShemaMediaItem.project_id == project_id)
        .order_by(ShemaMediaItem.created_at, ShemaMediaItem.id)
    )
    photos, videos = [], []
    for row in (await db.execute(stmt)).scalars():
        decision = recorded_decision(row)
        if row.kind == ShemaMediaKind.PHOTO:
            photos.append(ShemaMediaPhoto(caption=row.caption, authorization=decision))
        else:
            videos.append(
                ShemaProjectVideo(
                    url=row.url or "", caption=row.caption or None, authorization=decision
                )
            )
    return photos, videos


async def _history(db: AsyncSession, project_id: str) -> list[ShemaProgressHistoryEntry]:
    """The progress trail, oldest first — what ``progressAsOf`` and the ETEN report read.

    Ordered by ``created_at`` under ``entry_date``, which is the reason that column is stamped
    from Python rather than from the transaction's clock
    (``app/db/models/shema_progress.py``): two entries on one day would otherwise come back in
    an order nobody chose, and the deltas the screen renders are read off consecutive pairs.
    """
    stmt = (
        select(ShemaProgressEntry)
        .where(ShemaProgressEntry.project_id == project_id)
        .order_by(ShemaProgressEntry.entry_date, ShemaProgressEntry.created_at)
    )
    return [
        ShemaProgressHistoryEntry.model_validate(row) for row in (await db.execute(stmt)).scalars()
    ]


async def _health_history(db: AsyncSession, project_id: str) -> list[ShemaHealthAssessmentEntry]:
    """Every assessment, oldest first. BE-07 appends; this only reads.

    The flat fields on the record are a **projection of the newest entry** and never a second
    truth, so a screen that shows both is showing one fact twice on purpose — the history is
    what makes a backdated assessment visible instead of silently winning.
    """
    stmt = (
        select(ShemaHealthAssessment)
        .where(ShemaHealthAssessment.project_id == project_id)
        .order_by(ShemaHealthAssessment.assessment_date, ShemaHealthAssessment.created_at)
    )
    return [
        ShemaHealthAssessmentEntry.model_validate(row) for row in (await db.execute(stmt)).scalars()
    ]


async def build_record(
    db: AsyncSession, project: ShemaProject, *, today: date
) -> ShemaProjectRecord:
    """One record, assembled — for a caller that has already decided it may read this row.

    Separate from :func:`read_record` because the write path has the row in hand and has
    already answered the scope question; re-deriving it would be a second place for the answer
    to differ. Nothing here checks anything, which is why it takes a row and not an id.

    ``today`` is injected rather than read, so the whole path from the request to a staleness
    band is a pure function of a day the caller names — BE-05's reason, and what lets a test
    move the calendar without moving the machine.
    """
    needs = await _needs(db, project.id)
    materials = await _materials(db, project.id)
    photos, videos = await _media(db, project.id)
    history = await _history(db, project.id)
    assessments = await _health_history(db, project.id)

    record = ShemaProjectRecord.model_validate(project).model_copy(
        update={
            "needs_items": needs,
            "materials": materials,
            "media_photos": photos or None,
            "media_videos": videos or None,
            "progress_history": history,
            "health_history": assessments or None,
            "last_progress_date": history[-1].date if history else None,
        }
    )
    derived = derive(record, today, region=project.region_key)
    return record.model_copy(update={"derived": ShemaProjectDerived.of(derived)})


async def read_record(
    db: AsyncSession,
    scope: RegionScope,
    project_id: str,
    *,
    user: User,
    today: date,
) -> ShemaProjectRecord:
    """The ficha's answer: one project inside ``scope``, whole, or ``NotFoundError``.

    ``scope`` is positional and has no default: a keyword with a permissive default is how a
    scope stops being applied, and there is no unscoped spelling of this call.
    """
    project = await get_project(db, scope, project_id, user=user, operation="read_record")
    return await build_record(db, project, today=today)


async def read_changes_since(
    db: AsyncSession, scope: RegionScope, project_id: str, version: int, *, user: User
) -> ChangesSince:
    """What moved on a record after ``version`` — the trail, for a caller holding an id.

    Scoped exactly as the record read is: the trail says who edited what, which is a fact about
    the record and travels no further than the record does. It is here rather than in
    ``_audit.py`` because that file takes a row it trusts, and this one is the door.
    """
    project = await get_project(db, scope, project_id, user=user, operation="read_changes_since")
    return await changes_since(db, project, version)
