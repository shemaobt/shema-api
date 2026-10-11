"""The record read — one project, whole, as the ficha's ten tabs need it.

``get_project`` is the scoped row and stays exactly that. This is the screen built on it: the
row, plus the five collections that do not live on it, plus the day's derivations.

**Five reads and not one join**, which is BE-05's finding on the collection and holds here for
a narrower reason: the five children are five one-to-many relations, so a single joined
statement returns their cross product — five needs and four photos on one project is twenty
rows to regroup in Python — and every one of them is keyed on an id that came out of the
scoped read, so none can reach a project the caller cannot. The property ``_scope.py`` states
as *there is no unscoped query to call* holds here by there being no id to query with.

**This file names no guarded column.** The record is built for its reader (OBT-528): a
coordination reader gets the true place and everybody else the region, and the reduction is
applied by the act of validating the row into
:class:`~app.models.shema_record.ShemaProjectRecord` for that reader — this file only says who
reads. The needs and the assessments join the record after it is built, so the text they
carry is held back by ``_redaction.free_text_as_read`` instead, on the same withheld record for
the same readers (OBT-556). The prayer request is the same shape of answer from its own owner
(BE-09): a reader outside ``_consent.PRAYER_AUDIENCE`` gets a request nobody authorized as
``""``, and ``_consent.request_as_read`` is what decides it. A team's health is the third
(OBT-553): a reader outside ``_health_audience.HEALTH_READERS`` gets every health field as a
project nobody has assessed holds it — the projection, the history and the pastoral follow-up —
and ``_health_audience.health_as_read`` decides it. All are asked in :func:`_record_as_read`,
the one place this record is reduced for who reads it beyond the place, and applied **before**
``derive``, so the record's tone and health score cannot say what its fields no longer do. The
three authorization columns behind every ``authorization`` key are still read by their one
owner: ``_media_sharing.recorded_decision`` builds the shape and hands it over, and
``tests/test_shema/test_privacy_owners.py`` is what keeps that true of the next file too.

**The write path re-reads through here.** FE-44 §9.3 requires the response to carry *the
recomputed record, including the new progressHistory entry*, because the record screen renders
what the save actually wrote — so the create, the patch and the read answer one shape built by
one function, and a field that appears on the read cannot be missing from the save's reply.
"""

from __future__ import annotations

from datetime import date
from typing import Any

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
from app.services.shema._consent import request_as_read
from app.services.shema._health_audience import health_as_read
from app.services.shema._media_sharing import recorded_decision
from app.services.shema._redaction import free_text_as_read
from app.services.shema._scope import Readership, RegionScope
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
            photos.append(ShemaMediaPhoto(id=row.id, caption=row.caption, authorization=decision))
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


def _record_as_read(
    project: ShemaProject, record: ShemaProjectRecord, readership: Readership
) -> dict[str, Any]:
    """What this reader may not read on the record, beyond the place — one update, or nothing.

    The place and the record's own free text are the shape's (``LeavingShape.read_by``). What
    else depends on who reads is asked here and nowhere else in this file, each of its own
    owner: the prayer request of ``_consent.py``, the text the needs and the assessments carry
    into a withheld record of ``_redaction.py`` (OBT-556), and a team's health of
    ``_health_audience.py`` (OBT-553).

    **The health answer is spread last, and that order is the rule.** Both of the last two
    answer ``health_history``: the withheld record's history without its notes, and ``None`` for
    a reader outside the health readers. An OBT Lab reading a withheld record is the first; a
    caller outside both lists is both, and the stricter answer has to be the one that stays.
    Since OBT-571 the Resource Circle is neither on a project in its own scope: it reads the
    truth and the health.
    """
    return {
        **request_as_read(project, reads_withheld=readership.withheld_prayer),
        **free_text_as_read(project, readership.reader_of(project.region_key), record),
        **health_as_read(record, reads_health=readership.reads_health),
    }


async def build_record(
    db: AsyncSession, project: ShemaProject, *, readership: Readership, today: date
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

    reader = readership.reader_of(project.region_key)
    joined = ShemaProjectRecord.read_by(project, reader).model_copy(
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
    record = joined.model_copy(update=_record_as_read(project, joined, readership))
    derived = derive(record, today, region=project.region_key)
    return record.model_copy(update={"derived": ShemaProjectDerived.of(derived)})


async def read_record(
    db: AsyncSession,
    scope: RegionScope,
    project_id: str,
    *,
    readership: Readership,
    user: User,
    today: date,
) -> ShemaProjectRecord:
    """The ficha's answer: one project inside ``scope``, whole, or ``NotFoundError``.

    ``scope`` is positional and has no default: a keyword with a permissive default is how a
    scope stops being applied, and there is no unscoped spelling of this call.
    """
    project = await get_project(db, scope, project_id, user=user, operation="read_record")
    return await build_record(db, project, readership=readership, today=today)


async def read_changes_since(
    db: AsyncSession,
    scope: RegionScope,
    project_id: str,
    version: int,
    *,
    readership: Readership,
    user: User,
) -> ChangesSince:
    """What moved on a record after ``version`` — the trail, for a caller holding an id.

    Scoped exactly as the record read is: the trail says who edited what, which is a fact about
    the record and travels no further than the record does — nor further than its reader's read
    of it (OBT-556), which is why ``readership`` is asked for. It is here rather than in
    ``_audit.py`` because that file takes a row it trusts, and this one is the door.
    """
    project = await get_project(db, scope, project_id, user=user, operation="read_changes_since")
    return await changes_since(db, project, version, readership=readership)
