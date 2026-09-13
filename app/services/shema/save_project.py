"""The record's write — a create, a partial update, and the guard that makes both safe.

**The problem this file exists for is not the payload, it is the second coordinator.** Several
people edit one record, sometimes inside one meeting, and last-write-wins discards work in
silence. So every update states the version it read, the write lands only while that version
is still current, and a refusal carries enough for the screen to say *what* moved and *who*
moved it (``_audit.py``'s :class:`~app.services.shema._audit.ChangesSince`).

**The guard is required, and that is a decision against this repository's own precedent.**
``app/services/sound_necklace/autosave_state.py`` makes its ``If-Match`` optional — *"without
it the write is unconditional, which is what a single editor autosaving in a loop wants"* —
and it is right about its own product: there the writer is one tab saving its own session.
Here the writer is one of several coordinators, and an optional guard is last-write-wins one
forgotten header away. A client that cannot say which version it read has no basis for
overwriting one.

**The order, inside one transaction with one commit under all of it**, which is the sibling's
shape (``docs/resource_requests.md`` §4.5) and the reason a partial progress batch cannot
exist:

1. the record, **inside the caller's scope** — out of scope is refused exactly as absent is;
2. the version, against what the client read;
3. the merged view, built and validated **before anything is applied** — every bad row in a
   batch named at once, and nothing written for any of them;
4. the diff; **a save that changed nothing stops here**, writing nothing and stamping nobody;
5. the version bump, as a conditional ``UPDATE`` that is also the race guard;
6. the row, the progress entry and the trail — staged together, committed once.

**Step 4 is why a no-op save does not invalidate everybody else.** Stamping ``updated_by`` and
bumping the version unconditionally would make pressing save on an untouched tab refuse every
other editor in the meeting, which turns the guard into a reason not to press save.

**Step 5 is the race guard and not only the client guard.** Step 2 catches the client that
read version 7 and is saving over version 9; it cannot catch two requests that both read 7,
because both pass. The conditional ``UPDATE`` can: the first sets 8 and holds the row until it
commits, the second re-evaluates ``version = 7`` against a committed 8 and matches nothing.
SQLAlchemy's ``version_id_col`` would do the same thing at the mapper and was refused — it
raises ``StaleDataError`` from *any* flush of this table, so BE-07's and BE-08's own writes
would meet a SQLAlchemy exception with no handler and answer 500 where this answers 409.

This file may read ``location``: it does so through ``_redaction.derive_region``, which is the
column's one reader, so ``tests/test_shema/test_privacy_owners.py`` needs no allowlist entry
for it.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError, ValidationError
from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.models.shema import ShemaProjectCreate, ShemaProjectUpdate
from app.services.shema import _audit
from app.services.shema._audit import ChangesSince
from app.services.shema._progress import (
    Aggregates,
    ProgressSource,
    record_progress,
    with_rolled_aggregates,
)
from app.services.shema._redaction import derive_region, log_reference
from app.services.shema._scope import RegionScope, reaches, refuse_out_of_scope, visible_projects

logger = logging.getLogger(__name__)

#: The four the roll-up writes and the history entry measures.
_AGGREGATE_COLUMNS = (
    "translated_units",
    "community_checked_units",
    "approved_units",
    "total_units",
)


class RecordVersionConflict(ConflictError):
    """A save from a version that is no longer current, carrying what moved since.

    Its own exception rather than a bare :class:`~app.core.exceptions.ConflictError` for the
    reason ``app/core/exceptions.py`` gives for ``SessionLockChanged``: the handler is what
    puts the body on the wire, and a generic ``CONFLICT`` says *stale version* without the
    version — or the fields, or the name — that the screen needs to explain itself. The router
    renders :attr:`changes`; nothing else in this module raises this.
    """

    def __init__(self, changes: ChangesSince, *, expected: int | None) -> None:
        super().__init__("This record was saved by somebody else. Reload it before saving again.")
        self.changes = changes
        self.expected = expected


def _aggregates(source: dict[str, Any]) -> Aggregates:
    return Aggregates(
        translated=source["translated_units"],
        community=source["community_checked_units"],
        approved=source["approved_units"],
        total=source["total_units"],
    )


def _rows(value: Any) -> list[dict[str, Any]]:
    """A progress table as the column stores it — camelCase dictionaries, never ``None``.

    The typed row models are validated on the way in and dumped **by alias**, which is the one
    place this module's wire spelling reaches the database and is deliberate:
    ``app/models/shema_record.py``'s ``_DOCUMENT`` carries the argument — nothing queries
    inside these arrays, so a second spelling would be two translations bought for nothing.
    """
    if value is None:
        return []
    return [
        row.model_dump(by_alias=True) if hasattr(row, "model_dump") else dict(row) for row in value
    ]


def _merged(project: ShemaProject, payload: ShemaProjectUpdate) -> dict[str, Any]:
    """What the row would hold, built without touching it.

    Built and validated before a single attribute is applied, which is what makes *a partial
    failure applies nothing* a property of the order rather than of a rollback: the transaction
    would undo a half-applied batch anyway, but a function that mutates and then checks is one
    early ``return`` away from being wrong.

    ``coords`` expands into the two columns the database has, because ``[0, 0]`` is *no
    coordinate* and that is a fact about the pair — the record keeps the number the export gave
    and nothing here decides what it means.
    """
    sent = {name: getattr(payload, name) for name in payload.model_fields_set}
    merged = {column: getattr(project, column) for column in _audit.AUDITED_COLUMNS}

    coords = sent.pop("coords", None)
    if coords is not None:
        merged["longitude"], merged["latitude"] = float(coords[0]), float(coords[1])
    sent.pop("id", None)

    for column, value in sent.items():
        merged[column] = value

    for column in ("book_progress", "story_progress"):
        merged[column] = _rows(merged[column])
    if merged["other_progress"] is not None:
        merged["other_progress"] = _rows(merged["other_progress"])
    merged["phases"] = _rows(merged["phases"])

    rolled = with_rolled_aggregates(
        book_progress=merged["book_progress"],
        other_progress=merged["other_progress"],
        stated=_aggregates(merged),
    )
    merged["translated_units"] = rolled.translated
    merged["community_checked_units"] = rolled.community
    merged["approved_units"] = rolled.approved
    merged["total_units"] = rolled.total
    return merged


def _refuse_impossible_dates(merged: dict[str, Any]) -> None:
    """The cross-record half of *sane ranges* — the half a request model cannot see.

    A ``PATCH`` that sends only a ``deadline`` is checked against the ``start_date`` already on
    the row, so the rule has to be read off the **merged** record and therefore lives in the
    service, where ``docs/api-conventions.md`` puts the cross-record rules. Nothing here
    duplicates a Pydantic check: the row-level progress rules are in
    ``app/models/shema_record.py`` and are about one payload, and this one is about two.

    **Only the orderings that cannot be true are refused**, and a deadline in the past is not
    one of them: 8 export records carry a ``start_date``, none carries a ``deadline``, and
    ``getDeadlineInfo`` already classifies an overdue one as a state the screen shows rather
    than an error. What is refused is a finish before a beginning.
    """
    start = merged.get("start_date")
    problems = [
        f"{label} {value.isoformat()} is before the start date {start.isoformat()}"
        for label, value in (("deadline", merged.get("deadline")),)
        if isinstance(start, date) and isinstance(value, date) and value < start
    ]
    if problems:
        raise ValidationError("; ".join(problems))


async def _bump_version(db: AsyncSession, project: ShemaProject, expected: int) -> int | None:
    """Move the version from ``expected`` to ``expected + 1``, or answer ``None``.

    The conditional ``UPDATE`` **is** the race guard — see the module docstring's step 5. It is
    issued before the row's own attributes are applied so that a lost race writes nothing at
    all, rather than writing and relying on the caller to roll back a session it shares with
    the rest of the request.

    ``synchronize_session=False`` because the ORM's copy is updated by hand a line later: the
    alternative asks SQLAlchemy to re-read a row it is about to write.
    """
    stmt = (
        update(ShemaProject)
        .where(ShemaProject.id == project.id, ShemaProject.version == expected)
        .values(version=expected + 1)
        .execution_options(synchronize_session=False)
    )
    if (await db.execute(stmt)).rowcount != 1:
        return None
    return expected + 1


async def save_project(
    db: AsyncSession,
    scope: RegionScope,
    project_id: str,
    payload: ShemaProjectUpdate,
    *,
    user: User,
    expected_version: int,
    day: date,
    source: ProgressSource | None = None,
) -> ShemaProject:
    """Apply a partial write to one record, or refuse it — the module docstring's six steps.

    ``scope`` is positional and has no default, for ``list_projects``'s stated reason: a
    keyword with a permissive default is how a scope stops being applied. **Writes are scoped
    by the same value as reads** (``docs/shema.md`` §6.1) — a regional coordinator who may read
    a region may write it, and the product has no third answer — so this starts at
    ``visible_projects`` exactly as the record read does, and a project outside the caller's
    reach is refused with the same ``NotFoundError`` for the same reason: a 403 on a direct id
    is the existence-without-detail answer delivered by status code.

    ``day`` is the actor's local day and is the caller's to state; ``source`` is BE-12's, and
    is here so that an imported update and a typed one are one path.
    """
    project = (
        await db.execute(visible_projects(scope).where(ShemaProject.id == project_id))
    ).scalar_one_or_none()
    if project is None:
        raise refuse_out_of_scope(scope, user=user, operation="save_project", project_id=project_id)

    if project.version != expected_version:
        raise RecordVersionConflict(
            await _audit.changes_since(db, project, expected_version), expected=expected_version
        )

    before = _audit.snapshot(project)
    merged = _merged(project, payload)
    _refuse_impossible_dates(merged)

    changed = [column for column in _audit.AUDITED_COLUMNS if before[column] != merged[column]]
    if not changed:
        return project

    version = await _bump_version(db, project, expected_version)
    if version is None:
        await db.refresh(project)
        raise RecordVersionConflict(
            await _audit.changes_since(db, project, expected_version), expected=expected_version
        )

    previous = _aggregates(before)
    for column in changed:
        setattr(project, column, merged[column])
    project.region_key = derive_region(project)
    project.version = version
    project.updated_by = user.id
    project.updated_by_name = _audit.author_name(user)

    if any(column in changed for column in _AGGREGATE_COLUMNS):
        entry = record_progress(
            project.id,
            previous=previous,
            current=_aggregates(merged),
            book_progress=merged["book_progress"],
            story_progress=merged["story_progress"],
            other_progress=merged["other_progress"],
            day=day,
            source=source,
        )
        if entry is not None:
            db.add(entry)

    _audit.record_edits(
        db,
        project,
        version=version,
        changes=_audit.field_changes(before, project),
        user=user,
    )
    await db.commit()
    await db.refresh(project)
    return project


async def create_project(
    db: AsyncSession,
    scope: RegionScope,
    payload: ShemaProjectCreate,
    *,
    user: User,
    day: date,
    source: ProgressSource | None = None,
) -> ShemaProject:
    """Mint the record at the slug the client already holds, or refuse the slug.

    **The id is the client's**, which is FE-44 §5.1's frozen decision: the export's slug is the
    address every screen, URL and saved view carries, and BE-16 does not mint new ones. So a
    create is an upsert's other half and the one thing it owns is the collision — a slug that
    exists is a :class:`~app.core.exceptions.ConflictError` naming it, never a silent overwrite
    of somebody else's record.

    **The scope is checked against the region the new record derives**, not against the caller's
    ability to create in general. A coordinator scoped to Africa may not file a project in Asia,
    and the check is here rather than at the guard because the region is a consequence of the
    ``location`` the payload carries — there is nothing to check until the payload is read.

    **This refusal is a 403 and not the 404 every other refusal in this module answers**, and
    the difference is what the two conceal. ``_scope.py``'s ``NotFoundError`` exists so that
    *this slug is real but not yours* cannot be told from *no such slug* — an oracle over rows
    the caller may not see. Here there is no row and no oracle: the caller chose the id and
    wrote the location, so the only fact in the answer is one they supplied. Saying *not found*
    about a record they are in the middle of creating would be a worse message for no privacy.

    **The row is added and flushed before the payload is read**, which is not an ordering
    accident: a Python-side ``default=`` is applied by the flush, so a merged view built off an
    unflushed object would write NULL into the 55 columns whose word for *nothing* is ``""``.
    It is also what makes the trail record the fields the creator actually typed rather than
    seventy-three rows of ``"" -> ""``. The ``INSERT`` is inside the caller's transaction and a
    refusal below leaves nothing behind.

    The trail's first rows are written here too: a create is a record arriving from nothing,
    and a trail that started only at the first edit could not say who filed it.
    """
    existing = (
        await db.execute(select(ShemaProject.id).where(ShemaProject.id == payload.id))
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"{payload.id}: a project already exists at this slug")

    project = ShemaProject(id=payload.id, version=1)
    db.add(project)
    await db.flush()

    before = _audit.snapshot(project)
    merged = _merged(project, payload)
    _refuse_impossible_dates(merged)

    for column in _audit.AUDITED_COLUMNS:
        setattr(project, column, merged[column])
    project.region_key = derive_region(project)
    project.updated_by = user.id
    project.updated_by_name = _audit.author_name(user)

    if not reaches(scope, project.region_key):
        logger.warning(
            "shema authorization refused: a record filed outside the caller's regions",
            extra={
                "shema_operation": "create_project",
                "shema_user_id": user.id,
                "shema_scope_global": scope.global_,
                "shema_scope_regions": sorted(scope.regions),
                **log_reference(project),
            },
        )
        raise AuthorizationError(
            f"{project.region_key.value}: outside the regions this account may write"
        )

    await db.flush()

    entry = record_progress(
        project.id,
        previous=None,
        current=_aggregates(merged),
        book_progress=merged["book_progress"],
        story_progress=merged["story_progress"],
        other_progress=merged["other_progress"],
        day=day,
        source=source,
    )
    if entry is not None:
        db.add(entry)

    _audit.record_edits(
        db, project, version=1, changes=_audit.field_changes(before, project), user=user
    )
    await db.commit()
    await db.refresh(project)
    return project
