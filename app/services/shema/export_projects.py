"""The projects export — the file, its header, and the record that it left.

``GET /api/shema/export/projects`` lands here. **An export is the moment data stops being
governed by this system**, so the issue's rule is one code path through the filters every other
read already uses, and never a payload assembled from rows:

1. **the projects are the caller's scope, read by the listing's own query** —
   :func:`~app.services.shema.list_projects.list_projects`, which starts at ``visible_projects``;
   a row outside the scope is not reachable from here, so it cannot be in the file;
2. **each row is a leaving shape validated off the row with no reader** —
   :class:`~app.models.shema_transfer.ExportedProject`, ``outside``: the place, the base and the
   contacts are reduced by the boundary before this file sees them, whoever exports;
3. **the prayer requests are** ``_consent.authorized_requests_by_project``'s **texts**, the one
   assembly of what may leave that the wall and the Pulse read too — the columns are never read
   here, and a request nobody authorized is not in the answer to copy;
4. **the open needs are counted by status** over ids that came out of the scoped read, with the
   facets' own ``OPEN_NEED_STATUSES``;
5. **the notes are asked of** ``can_export_notes`` **under the file's audience**, ``publico``,
   which answers no — and are read off the row only if it ever answers yes.

**The header is addressed, the rows are not.** How many places were withheld is announced to
coordination only (GATE-04, 1.3): ``withheld_note`` decides, told who the exporter is — the
region's coordination if they coordinate anything, as the Projetos screen addresses its own
notice. The rows stay ``outside`` either way; the exporter's reader reaches the header and
nothing else.

**Every file is logged before it is handed back**, in ``shema_exports``: who, when, the scope,
the format, how many rows and how many withheld, and which projects and requests went out, by
id. The file names its log row, so a copy found later leads back to it. The row is committed
before the response is written — a file that leaves unlogged is the failure the issue names,
and a logged file that failed to leave is only a false alarm.

**Why it is not a job to poll.** The issue's rule is *asynchronous rather than slow*, and the
export is not slow where it could be: the file is the caller's scope — the collection
``GET /api/shema/projects`` already answers in one request — read in three statements whatever
the number of projects (``tests/test_shema/test_transfer.py`` pins that they do not grow). What
does grow is the part with no I/O, a row validated and written per project, and that runs in a
worker thread (:func:`_write`), so a coordinator exporting two thousand projects does not hold
the event loop every other request is waiting on. The pull request carries the measurement; a
queued job would have changed FE-44 §9.12's ``GET`` into two routes and a store for a cost that
is not there to measure.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_export import ShemaExport
from app.db.models.shema_need import ShemaNeed
from app.models.shema_prayer import PulseLanguage
from app.models.shema_privacy import ShemaReader
from app.models.shema_transfer import (
    EXPORT_AUDIENCE,
    ExportedProject,
    ExportFormat,
    ExportMeta,
    export_copy,
    export_filename,
    render_csv,
    render_json,
    withheld_sentence,
)
from app.services.shema._audit import author_name
from app.services.shema._consent import AuthorizedRequest, authorized_requests_by_project
from app.services.shema._media_sharing import can_export_notes
from app.services.shema._redaction import withheld_note
from app.services.shema._scope import Readership, RegionScope
from app.services.shema.eten_report import _scope_key
from app.services.shema.list_projects import list_projects
from app.utils.shema_facets import OPEN_NEED_STATUSES

logger = logging.getLogger(__name__)

#: What each format is served as. ``charset`` is named because the CSV opens with a BOM and a
#: client that guessed Latin-1 would print it.
MEDIA_TYPES: dict[ExportFormat, str] = {
    ExportFormat.JSON: "application/json; charset=utf-8",
    ExportFormat.CSV: "text/csv; charset=utf-8",
}


class ExportFile(NamedTuple):
    """The file, and the name and type it is served under."""

    filename: str
    media_type: str
    body: str


async def _open_needs(db: AsyncSession, ids: list[str]) -> dict[str, int]:
    """How many open needs each project in ``ids`` has — one ``GROUP BY``, keyed on scoped ids."""
    if not ids:
        return {}
    stmt = (
        select(ShemaNeed.project_id, func.count())
        .where(ShemaNeed.project_id.in_(ids), ShemaNeed.status.in_(OPEN_NEED_STATUSES))
        .group_by(ShemaNeed.project_id)
    )
    return dict((await db.execute(stmt)).tuples().all())


class _Header(NamedTuple):
    """What the header knows before a row is built: which record it is, when, by whom, where."""

    export_id: str
    generated_at: datetime
    generated_by: str
    scope: list[str] | None
    addressee: ShemaReader


class _Written(NamedTuple):
    body: str
    withheld: int


def _write(
    projects: Sequence[ShemaProject],
    authorized: Mapping[str, Sequence[AuthorizedRequest]],
    open_needs: Mapping[str, int],
    header: _Header,
    file_format: ExportFormat,
    language: PulseLanguage,
) -> _Written:
    """The rows through the boundary, the header addressed, the file rendered — no I/O at all.

    **Run off the event loop** (:func:`export_projects`), because it is the one part of an export
    that grows with the collection: validating a row per project and writing it out. Every value it
    reads is already loaded — the rows came whole from one ``SELECT`` and the requests and the
    counts are plain values — so it touches no session and needs none.
    """
    notes_leave = can_export_notes(EXPORT_AUDIENCE)
    rows = [
        ExportedProject.model_validate(project).model_copy(
            update={
                "open_needs": open_needs.get(project.id, 0),
                "shared_prayer_requests": [request.text for request in authorized[project.id]],
                "exported_notes": project.notes if notes_leave else None,
            }
        )
        for project in projects
    ]
    withheld = withheld_note(rows, header.addressee)
    contains, confidential = export_copy(language)
    meta = ExportMeta(
        export_id=header.export_id,
        contains=contains,
        confidential=confidential,
        generated_at=header.generated_at,
        generated_by=header.generated_by,
        scope=header.scope,
        format=file_format,
        project_count=len(rows),
        locations_withheld=withheld,
        withheld_note=withheld_sentence(withheld, language),
    )
    body = (
        render_json(meta, rows)
        if file_format is ExportFormat.JSON
        else render_csv(meta, rows, language)
    )
    return _Written(body=body, withheld=sum(1 for row in rows if row.location_withheld))


async def export_projects(
    db: AsyncSession,
    scope: RegionScope,
    *,
    readership: Readership,
    user: User,
    file_format: ExportFormat,
    language: PulseLanguage,
    now: datetime,
) -> ExportFile:
    """The caller's scope as a file in ``file_format``, headed in ``language`` — and logged.

    ``scope`` is positional and has no default, for ``list_projects``' stated reason.
    ``readership`` addresses the header and builds no row. ``now`` is injected, as every read
    here injects its day, and is the instant both the file and its log row carry.
    """
    projects = await list_projects(db, scope)
    ids = [project.id for project in projects]
    authorized = await authorized_requests_by_project(db, projects)
    open_needs = await _open_needs(db, ids)

    export_id = str(uuid.uuid4())
    addressee = ShemaReader.COORDINATION if readership.coordinates_anything else ShemaReader.OTHER
    header = _Header(
        export_id=export_id,
        generated_at=now,
        generated_by=author_name(user),
        scope=scope.wire,
        addressee=addressee,
    )
    written = await asyncio.to_thread(
        _write, projects, authorized, open_needs, header, file_format, language
    )

    request_ids = [request.id for project in projects for request in authorized[project.id]]
    db.add(
        ShemaExport(
            id=export_id,
            exported_by=user.id,
            exported_by_name=header.generated_by,
            scope_key=_scope_key(scope),
            format=file_format.value,
            project_count=len(projects),
            withheld_count=written.withheld,
            project_ids=ids,
            request_ids=request_ids,
            created_at=now,
        )
    )
    await db.commit()

    logger.info(
        "shema projects exported",
        extra={
            "shema_operation": "export_projects",
            "shema_export_id": export_id,
            "shema_user_id": user.id,
            "shema_scope_global": scope.global_,
            "shema_scope_regions": sorted(scope.regions),
            "shema_format": file_format.value,
            "shema_projects": len(projects),
            "shema_withheld": written.withheld,
            "shema_requests": len(request_ids),
        },
    )
    return ExportFile(
        filename=export_filename(now.date(), file_format),
        media_type=MEDIA_TYPES[file_format],
        body=written.body,
    )
