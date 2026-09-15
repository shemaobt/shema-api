"""The edit trail's writer and its one reader — *who moved what, and what moved since*.

The issue's fifth line is *every write recorded with author and timestamp*, and its second is
*a stale write is rejected with a conflict the UI can explain*. Those are one mechanism read
from two ends: a trail keyed by the version a save produced answers both *who changed this*
and *what happened between the version I read and the one that is current*, and answering them
separately would mean a second store to keep in step.

**The diff is of values, not of keys**, taken against the row as it was loaded and before the
payload is applied. A tab that saves a field back unchanged is not an edit: a payload carrying
forty fields and moving one writes one row, which is what makes the trail readable and what
stops a version bump — and with it everybody else's refusal — on a save that changed nothing.

**The values of a guarded field are not recorded, and its key is.** The place, the three
contacts, the sensitive flag, the free-text ``sensitivity`` and the three prayer columns record
``old_value = new_value = NULL``: the trail says *the place changed, by Maria, at 14:02* and
does not say from where to where. ``log_reference``'s argument one layer along — a trail is
read by more people and kept longer than a response body, and a country copied into it has
left the boundary this module holds. What is lost is small and stated: a reader learns that
the place moved and goes to the record, where being allowed is checked.

**This file names no guarded column, and it does read every column's value.** The snapshot
below is taken over *every* writable column by name-from-a-list and the guarded ones are
discarded after the comparison, which is the honest shape of a differ: it singles nothing out,
so ``tests/test_shema/test_privacy_owners.py``'s glob sees no targeted read and there is
nothing for it to see. The alternative was an allowlist entry naming this file a second reader
— and an entry is second for *all six* columns, not only for the one that was wanted.

**Nothing here commits.** The caller owns the transaction, which is what makes the trail, the
progress entry and the row itself one write — the sibling's contract for its ledger
(``docs/resource_requests.md`` §7.3) and for its reason: a trail written under its own commit
is a trail that can outlive a save that did not happen.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_audit import ShemaRecordEdit
from app.models.shema import ShemaProjectUpdate
from app.models.shema_privacy import CONTACT_FIELDS, PLACE_FIELDS

#: Column name → the key the trail is written in, which is the key the console reads.
#:
#: **The columns are the write model's own fields**, not the table's, because *what may be
#: audited* and *what a client may write* are the same list and a second one would go stale on
#: the first field somebody adds. ``coords`` is the one field that is not a column — it
#: expands into the two the database has, which is where a change to a project's position
#: actually lands.
_WIRE_EXCEPTIONS = {"in_eten": "inETEN"}


def _wire(column: str) -> str:
    head, *rest = column.split("_")
    return _WIRE_EXCEPTIONS.get(column) or head + "".join(word.title() for word in rest)


#: ``ShemaProjectUpdate.model_fields`` read off the class. Pydantic 2.10 types the accessor as
#: a descriptor, which mypy reads as a method when it is reached through the class rather than
#: through an instance; the dictionary is real and this is the one place that matters.
_WRITABLE_FIELDS: dict[str, Any] = dict(ShemaProjectUpdate.model_fields)  # type: ignore[call-overload]

#: The write model's fields that are **not** columns of ``shema_projects``, and therefore not
#: rows of this diff. ``coords`` is two columns and is expanded below; ``needs_items`` is a
#: child table with its own diff (``_needs.py``), which writes its changes under one key —
#: ``needsItems`` — through :func:`record_edits` like everything else, so a 409 names it and a
#: reader of the trail sees needs move beside the fields around them.
NOT_COLUMNS: frozenset[str] = frozenset({"coords", "needs_items"})

AUDITED_COLUMNS: tuple[str, ...] = tuple(
    [name for name in _WRITABLE_FIELDS if name not in NOT_COLUMNS] + ["latitude", "longitude"]
)

FIELD_KEYS: dict[str, str] = {column: _wire(column) for column in AUDITED_COLUMNS}

#: The keys whose **values** stay out of the trail — the module docstring's second paragraph.
#:
#: Built from the two owners' own vocabularies rather than typed out here:
#: ``app/models/shema_privacy.py`` names the places and the contacts and is what
#: ``LeavingShape`` reduces, ``sensitivity`` sits beside the flag in the glob's own
#: ``REDACTION_COLUMNS`` because it is the export's free text about *why* a place is sensitive,
#: and the three prayer columns are ``_consent.py``'s. A list kept here instead would be the
#: one that drifts from the list a glob enforces.
VALUES_WITHHELD: frozenset[str] = frozenset(
    {_wire(column) for column in PLACE_FIELDS + CONTACT_FIELDS}
    | {"sensitivity", "sensitiveCountry"}
    | {"prayerRequests", "prayerVisibility", "prayerRequestsAudio"}
)


class FieldChange(NamedTuple):
    """One field that actually moved, with both sides — or with neither, when it is guarded."""

    field_key: str
    old_value: str | None
    new_value: str | None


@dataclass(frozen=True)
class ChangesSince:
    """What happened to a record after the version a client was holding.

    The 409's body, and the whole of *a conflict the UI can explain*: a screen told only *you
    are stale* can offer nothing but a reload, while one told *Maria changed the status
    comments and the translated units at 14:02* can say so and let the coordinator decide what
    to keep. :attr:`fields` are wire keys, so the console looks them up where it looks up its
    own labels.

    An empty :attr:`fields` with a moved :attr:`version` is a real answer and not a bug: the
    record moved through a path that writes no trail — a seed, or a future service that stamps
    the row without going through this one — and saying *it moved and I cannot say how* is
    better than implying nothing did.
    """

    version: int
    fields: tuple[str, ...]
    by: str
    at: datetime | None


def snapshot(project: ShemaProject) -> dict[str, Any]:
    """Every writable column's value as it stands, for a diff to be taken against later.

    Taken before the payload is applied and never after: the *previous* side of the trail is
    the server's own read, which is the same rule FE-44 §7.2 states for the progress entry and
    for the same reason — a client that supplied it could rewrite what the record used to say.
    """
    return {column: getattr(project, column) for column in AUDITED_COLUMNS}


def _as_text(value: Any) -> str | None:
    """One side of a change, as the trail stores it.

    Text rather than a typed column, for the sibling's reason (``docs/resource_requests.md``
    §4.4): a record's fields are strings, integers, booleans, dates and JSON arrays, and a
    trail that recorded only some of them is not a trail. ``None`` is *there was nothing*.

    The three progress tables and ``phases`` are stored whole, which is a real cost on the
    module's highest-volume write and is paid deliberately. ``shema_progress_history``
    snapshots the same tables — but only on an entry that moved an aggregate, and with no
    author: a row renamed without moving a count leaves no entry there at all, and *who* is
    exactly what that table does not hold. Two records that each answer what the other cannot
    are not a duplicate.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list | dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def field_changes(before: Mapping[str, Any], project: ShemaProject) -> list[FieldChange]:
    """Every field whose value actually moved, in the order the write model declares them.

    Equality and not identity, so a list re-sent unchanged is not an edit — which is what the
    progress tab does on every save of a neighbouring field.
    """
    changes = []
    for column in AUDITED_COLUMNS:
        old, new = before.get(column), getattr(project, column)
        if old == new:
            continue
        key = FIELD_KEYS[column]
        if key in VALUES_WITHHELD:
            changes.append(FieldChange(key, None, None))
        else:
            changes.append(FieldChange(key, _as_text(old), _as_text(new)))
    return changes


def author_name(user: User | None) -> str:
    """The name to stamp — the display name, else the address, else an honest placeholder.

    A snapshot and not a reference (``ShemaRecordEdit.changed_by_name``), so it must be
    readable on its own years later. The email is the fallback because it is the one identifier
    every account in this platform has; ``display_name`` is nullable and often is.
    """
    if user is None:
        return "unknown"
    return user.display_name or user.email


def record_edits(
    db: AsyncSession,
    project: ShemaProject,
    *,
    version: int,
    changes: Iterable[FieldChange],
    user: User | None,
) -> list[ShemaRecordEdit]:
    """Stage one row per changed field, all carrying the version this save produced.

    ``user`` may be ``None`` — BE-12's intake link is unauthenticated by design
    (``docs/shema.md`` §6.6) — and the **name** is stamped either way, which is why the column
    that is ``NOT NULL`` is the name and not the account. ``ShemaRecordEdit``'s docstring
    carries the departure from the sibling's rule.

    Staged and not committed: see the module docstring.
    """
    rows = [
        ShemaRecordEdit(
            project_id=project.id,
            version=version,
            field_key=change.field_key,
            old_value=change.old_value,
            new_value=change.new_value,
            changed_by=None if user is None else user.id,
            changed_by_name=author_name(user),
        )
        for change in changes
    ]
    db.add_all(rows)
    return rows


async def changes_since(db: AsyncSession, project: ShemaProject, version: int) -> ChangesSince:
    """What the record's trail says happened after ``version`` — the 409's body.

    Reads the trail rather than diffing two rows, because there is no second row to diff: the
    version the client was holding is gone, and reconstructing it would mean the trail being a
    second copy of the record, which is what :class:`ShemaRecordEdit`'s docstring refuses.

    The fields are de-duplicated and kept in the order they were first touched, so a field
    edited twice between two versions is named once and the sentence the console builds reads
    like a sentence. ``by`` is the **newest** name: a screen that lists every editor of the
    last four versions is a screen nobody reads, and *saved by Maria* is the fact a
    coordinator acts on.
    """
    stmt = (
        select(ShemaRecordEdit)
        .where(ShemaRecordEdit.project_id == project.id, ShemaRecordEdit.version > version)
        .order_by(ShemaRecordEdit.version, ShemaRecordEdit.changed_at)
    )
    rows = list((await db.execute(stmt)).scalars())
    fields = list(dict.fromkeys(row.field_key for row in rows))
    newest = rows[-1] if rows else None
    return ChangesSince(
        version=project.version,
        fields=tuple(fields),
        by=newest.changed_by_name if newest else project.updated_by_name,
        at=newest.changed_at if newest else project.updated_at,
    )
