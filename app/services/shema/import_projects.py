"""The projects import — a file of records, checked whole and applied as one write.

``POST /api/shema/import/projects`` lands here. **Import is the export's inverse risk**: untrusted
input, which has to meet the same rules as any write, applied atomically, and which must not be a
way around authorization. Four steps, and the order is the design:

1. **the file is read and recognised** — JSON, not the report this module exports (the wrapper,
   a row of it, a payload that says it was reduced, or the CSV by the sentence it opens with),
   and a list;
2. **every record is checked before anything is applied** — by the write's own model,
   :class:`~app.models.shema.ShemaProjectCreate`, so vocabulary and shape are the create's
   (FE-44 §8.4: *by vocabulary and shape, not by* ``typeof``); the first broken record refuses the
   file with its 1-based index, and a repeated id refuses it too. Nothing has been read from the
   database yet;
3. **every record is applied through the write path** — an id the caller's scope reaches is
   ``save_project`` at its current version, any other id is ``create_project`` — so the region
   scope, the reader's fields (OBT-528), the prayer request's reader (BE-09), the version guard,
   the trail and the notices are the ones a typed save meets;
4. **the file commits once.** Both writers take ``commit=False`` here, so a refusal on the tenth
   record rolls the first nine back with it — the half-applied import the issue calls worse than
   a refused one cannot happen.

**Nothing in the file authorizes anything.** ``prayerVisibility`` and the recording are dropped
before validation, and so are a need's ``prayerShared`` and ``acknowledged``: an imported request
arrives as the write path leaves any request whose authorization was not stated — a new one
unauthorized, a changed one unauthorized again (``_consent.request_written``,
``_consent.need_written``), and an unchanged one exactly as the organisation left it. The file can
neither publish a request nor withdraw one; both are a person's decision on the record. **The
sensitive flag moves one way**: a file may raise it and may not clear it on a withheld record
(``_redaction.never_lowered``).

**What the server owns is not taken from a file, and the answer says so.** A whole ``Project``
carries the health projection, the progress history, the media, the materials, ``derived``,
``readAs``, ``locationWithheld`` and ``completedDate`` — every one of them written by the server
from something else, never by a client. They are dropped, and ``ignoredFields`` names them, so an
import is never read as having restored what it could not. The list is computed from the two
shapes — the record the console reads less the write it may send — so a key added to either is
classified by the change that added it. A key in neither is not the contract's, and the record
carrying it is refused.

**Nothing is deleted.** A project the file does not name is left as it is, which is the write's
own rule — absent means unchanged — and the console's *substituir* is INT-11's to reword.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import date
from typing import Any, NamedTuple

from pydantic import AliasChoices, BaseModel
from pydantic import ValidationError as PydanticValidationError
from pydantic.alias_generators import to_camel
from pydantic.fields import FieldInfo
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.models.shema import THE_BASE, ShemaProjectCreate
from app.models.shema_need import ShemaNeedWrite
from app.models.shema_privacy import ShemaReader
from app.models.shema_record import ShemaNeedItem, ShemaProjectRecord
from app.models.shema_transfer import (
    OPENING_SENTENCES,
    ExportedProject,
    ImportRefusal,
    ImportResult,
)
from app.services.shema._consent import REQUEST_AUDIO, REQUEST_VISIBILITY
from app.services.shema._redaction import never_lowered
from app.services.shema._scope import Readership, RegionScope, visible_projects
from app.services.shema.save_project import create_project, save_project

logger = logging.getLogger(__name__)


class ImportRefused(ValidationError):
    """A file refused before anything was applied, with the key the console's dialog names.

    Its own exception for ``RecordVersionConflict``'s reason: the handler is what puts the body on
    the wire, and the repository's ``BAD_REQUEST`` says *no* without the key, the item or the id
    the dialog needs to say *which*. ``errors`` is Pydantic's list without the input, so a refused
    record is never echoed back.
    """

    def __init__(
        self,
        key: ImportRefusal,
        detail: str,
        *,
        index: int | None = None,
        project_id: str | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(detail)
        self.key = key
        self.index = index
        self.project_id = project_id
        self.errors = errors or []


def _spellings(names: Iterable[str]) -> frozenset[str]:
    """Each field name as the house writes it and as the wire does."""
    return frozenset(spelling for name in names for spelling in (name, to_camel(name)))


def _accepted(model: type[BaseModel]) -> frozenset[str]:
    """Every key ``model`` accepts: the field names and every validation alias.

    ``model_fields`` read off the class, which Pydantic 2.10 types as a descriptor mypy takes for a
    method — ``_audit._WRITABLE_FIELDS``' note, and its ignore.
    """
    keys: set[str] = set()
    fields: dict[str, FieldInfo] = dict(model.model_fields)  # type: ignore[call-overload]
    for name, field in fields.items():
        keys.add(name)
        alias = field.validation_alias
        if isinstance(alias, str):
            keys.add(alias)
        elif isinstance(alias, AliasChoices):
            keys.update(choice for choice in alias.choices if isinstance(choice, str))
    return frozenset(keys)


def _wire(shape: BaseModel) -> frozenset[str]:
    return frozenset(shape.model_dump(by_alias=True))


#: The keys the record write accepts, both spellings of the base included — its validator folds
#: ``ywamBase`` into ``team``.
WRITE_KEYS = _accepted(ShemaProjectCreate) | set(THE_BASE)
#: The keys of the ``Project`` the console reads (``ShemaProjectRecord``, FE-44's 76 key for key).
RECORD_KEYS = _wire(ShemaProjectRecord(id="-"))
#: What the server writes from something else and a file therefore cannot: dropped, and named.
#: The org chart's three role-holders are among them — the record read fills them from the
#: region's team, so a file holding the server's own answer is not refused for carrying it.
SERVER_OWNED = RECORD_KEYS - WRITE_KEYS
#: The authorization and the recording. The recording is a storage key, and a key from a file is
#: an address into the private bucket that nobody minted; the visibility is the consent itself.
NOT_FROM_A_FILE = _spellings((REQUEST_VISIBILITY, REQUEST_AUDIO))
#: The same two sets for a need: the acknowledgement's stamp is the server's, and the file may
#: neither share a need for prayer nor say that somebody saw it.
NEED_SERVER_OWNED = _wire(ShemaNeedItem(id="-")) - _accepted(ShemaNeedWrite)
NEED_NOT_FROM_A_FILE = _spellings(("prayer_shared", "acknowledged"))
NEEDS_KEYS = _spellings(("needs_items",))
#: The keys only the exported report carries — a row of it is recognised by any one of them.
EXPORT_ONLY_KEYS = (
    frozenset(ExportedProject(id="-").as_row()) - RECORD_KEYS - WRITE_KEYS - {"notes"}
)
#: The one reading a payload may say it was built for and still carry the truth.
_TRUTH = ShemaReader.COORDINATION.value


class _Record(NamedTuple):
    position: int
    kept: dict[str, Any]
    payload: ShemaProjectCreate


def _refuse_constant(constant: str) -> Any:
    raise ValueError(f"{constant} is not JSON")


def _parse(raw: bytes) -> Any:
    """The file as JSON, or the refusal that says what it is instead.

    ``utf-8-sig``, so a file saved with a BOM is read rather than refused. ``NaN`` and
    ``Infinity`` are refused with the rest of what RFC 8259 does not allow: Python's reader takes
    them, and a coordinate of ``NaN`` is a value nobody meant.
    """
    try:
        text = raw.decode("utf-8-sig")
        return json.loads(text, parse_constant=_refuse_constant)
    except (UnicodeDecodeError, ValueError):
        pass
    opening = raw.decode("utf-8-sig", errors="replace").lstrip().lstrip('"')
    if opening.startswith(OPENING_SENTENCES):
        raise ImportRefused(ImportRefusal.IS_EXPORT, "this is the exported report, not a list")
    raise ImportRefused(ImportRefusal.INVALID_JSON, "the file could not be read as JSON")


def _is_the_report(parsed: Any) -> bool:
    """The exported file's own wrapper — ``{meta, projects}``, or either half of it."""
    return isinstance(parsed, dict) and ("projects" in parsed or "meta" in parsed)


def _is_reduced(entry: Any) -> bool:
    """Whether ``entry`` is a row of the report, or a payload that says it was reduced.

    **A check, not a naming convention.** The report's rows carry keys no record has
    (:data:`EXPORT_ONLY_KEYS`), and every leaving shape says whether the payload in hand is the
    truth: ``readAs`` on the console's reads, ``locationWithheld`` on everything. A payload whose
    place is withheld and which was not read as coordination holds the region where the place
    was — importing it would overwrite the truth with the reduction, which is the destructive
    round trip the refusal exists for.
    """
    if not isinstance(entry, dict):
        return False
    if EXPORT_ONLY_KEYS & entry.keys():
        return True
    read_as = entry.get("readAs")
    if read_as is not None and read_as != _TRUTH:
        return True
    return entry.get("locationWithheld") is True and read_as != _TRUTH


def _strip(entry: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
    """``entry`` less what a file may not set, and the names of what was dropped."""
    kept: dict[str, Any] = {}
    dropped: set[str] = set()
    for key, value in entry.items():
        if key in SERVER_OWNED or key in NOT_FROM_A_FILE:
            dropped.add(key)
            continue
        if key in NEEDS_KEYS and isinstance(value, list):
            value = [_strip_need(item, dropped) for item in value]
        kept[key] = value
    return kept, dropped


def _strip_need(item: Any, dropped: set[str]) -> Any:
    if not isinstance(item, dict):
        return item
    kept: dict[str, Any] = {}
    for key, value in item.items():
        if key in NEED_SERVER_OWNED or key in NEED_NOT_FROM_A_FILE:
            dropped.add(f"needsItems[].{key}")
            continue
        kept[key] = value
    return kept


def _faults(refused: PydanticValidationError) -> list[dict[str, Any]]:
    return [
        {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
        for error in refused.errors(include_url=False, include_context=False, include_input=False)
    ]


def read_import(raw: bytes) -> tuple[list[_Record], set[str]]:
    """Every record of the file, checked — or the refusal of the whole file.

    Pure: nothing is read from the database and nothing is written, so *validates everything
    before applying anything* is a property of the order the two halves run in.
    """
    parsed = _parse(raw)
    if _is_the_report(parsed):
        raise ImportRefused(ImportRefusal.IS_EXPORT, "this is the exported report, not a list")
    if not isinstance(parsed, list):
        raise ImportRefused(ImportRefusal.NOT_LIST, "the file is not a list of projects")
    if any(_is_reduced(entry) for entry in parsed):
        raise ImportRefused(
            ImportRefusal.IS_EXPORT, "these records were reduced before they left, not a list"
        )

    records: list[_Record] = []
    seen: set[str] = set()
    ignored: set[str] = set()
    for index, entry in enumerate(parsed, start=1):
        if not isinstance(entry, dict):
            raise ImportRefused(
                ImportRefusal.BAD_RECORD, f"item {index} is not a project", index=index
            )
        kept, dropped = _strip(entry)
        try:
            payload = ShemaProjectCreate.model_validate(kept)
        except PydanticValidationError as refused:
            raise ImportRefused(
                ImportRefusal.BAD_RECORD,
                f"item {index} is not a valid project record",
                index=index,
                errors=_faults(refused),
            ) from None
        if payload.id in seen:
            raise ImportRefused(
                ImportRefusal.DUPLICATE_ID,
                f"{payload.id} appears more than once",
                project_id=payload.id,
            )
        seen.add(payload.id)
        ignored |= dropped
        records.append(_Record(index, kept, payload))
    return records, ignored


def _at(record: _Record, refused: Exception) -> Exception:
    """The write path's own refusal, said about the item that met it — same class, same status."""
    for kind in (AuthorizationError, NotFoundError, ConflictError, ValidationError):
        if isinstance(refused, kind):
            return kind(f"item {record.position} ({record.payload.id}): {refused}")
    return refused


def _unlowered(project: ShemaProject, record: _Record) -> tuple[ShemaProjectCreate, bool]:
    """The record's payload with the flag kept raised on a withheld project, and whether it was."""
    payload = record.payload
    sent = {name: getattr(payload, name) for name in payload.model_fields_set}
    kept = never_lowered(project, sent)
    if kept == sent:
        return payload, False
    return ShemaProjectCreate.model_validate(kept), True


async def import_projects(
    db: AsyncSession,
    scope: RegionScope,
    raw: bytes,
    *,
    readership: Readership,
    user: User,
    day: date,
) -> ImportResult:
    """Apply the file ``raw`` inside ``scope``, as ``user`` — every record, or none of them.

    ``scope`` is positional and has no default, for ``list_projects``' stated reason, and it is
    the same value a typed save takes: an import reaches exactly as far as a write does.
    ``readership`` is the importer's, because an import is a person writing the record. ``day``
    is the importer's local day, which the progress entries a record moves are stamped with.
    """
    records, ignored = read_import(raw)
    ids = [record.payload.id for record in records]
    existing = {
        project.id: project
        for project in (
            await db.execute(visible_projects(scope).where(ShemaProject.id.in_(ids)))
        ).scalars()
    }

    created = 0
    record: _Record | None = None
    try:
        for record in records:
            project = existing.get(record.payload.id)
            if project is None:
                await create_project(db, scope, record.payload, user=user, day=day, commit=False)
                created += 1
                continue
            payload, kept_raised = _unlowered(project, record)
            if kept_raised:
                ignored.add("sensitiveCountry")
            await save_project(
                db,
                scope,
                project.id,
                payload,
                readership=readership,
                user=user,
                expected_version=project.version,
                day=day,
                commit=False,
            )
        await db.commit()
    except (AuthorizationError, ConflictError, NotFoundError, ValidationError) as refused:
        await db.rollback()
        if record is None:
            raise
        raise _at(record, refused) from refused

    logger.info(
        "shema projects imported",
        extra={
            "shema_operation": "import_projects",
            "shema_user_id": user.id,
            "shema_scope_global": scope.global_,
            "shema_scope_regions": sorted(scope.regions),
            "shema_created": created,
            "shema_updated": len(records) - created,
        },
    )
    return ImportResult(applied=len(records), ignored_fields=sorted(ignored))
