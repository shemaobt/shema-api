"""``/api/shema/export/projects`` and ``/api/shema/import/projects`` — FE-44 §9.12's two routes.

Each handler declares its dependencies, calls one service and returns what it answers: no query,
no filter, no role check of its own. The caller's reach arrives as a ``RegionScope`` and is handed
straight down (``docs/shema.md`` §6.2), and so is the caller's reader — **which is the one thing
here that needs its reason written down**, because ``tests/test_shema/test_privacy_owners.py``
keeps the routes that take it in a list somebody has to argue:

* the **export** takes it to address the file's header — how many places were withheld is
  coordination's to be told (GATE-04, 1.3) — and for nothing else: every row is built for
  ``outside``, whoever asked, and the service that builds them calls no ``read_by``;
* the **import** takes it because it is the import's door — only coordination imports — and
  because an import is a person writing the record, and ``save_project`` asks the writer's
  reader which fields they may write, as the two form imports do.

**Who may use them is not the same for the two.** The export is any Shemá role's, inside its
scope: the file is the scope the caller already reads, reduced for everybody. **The import is
coordination's** — ``globalStrategist``, a ``coordinator`` in its regions, the ``admin`` role, an
installation admin — because the file it restores is a whole record, and only coordination reads
one; ``import_projects.py``'s docstring carries the argument. The refusal is the service's, like
every other rule here.

**The export is a ``GET`` that writes**, for the ETEN report's reason (``eten.py``): the log row
is an audit of what the server handed out, not a change the caller asked for, and a file that
left without it is the one after-the-fact question nobody could answer.

**The import reads its body raw.** FastAPI would answer a body it cannot parse with its own 422,
and the console's dialog names five refusals of its own (``import_invalid_json`` among them), so
the bytes go to the service, which is where the file is read, recognised and checked.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.shema._deps import CurrentUser, Db, Reading, Scope
from app.api.shema.projects import (
    LOCAL_DAY_HEADER,
    PER_READER_CACHE_CONTROL,
    _conflict,
    _local_day,
)
from app.core.exceptions import ERROR_CODE_BAD_REQUEST
from app.models.shema_prayer import PulseLanguage
from app.models.shema_transfer import ExportFormat, ImportResult
from app.services.shema import (
    ImportRefused,
    RecordVersionConflict,
    export_projects,
    import_projects,
)

router = APIRouter()

_EXPORT_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_200_OK: {
        "description": "The file, headed with its provenance.",
        "content": {"application/json": {}, "text/csv": {}},
    }
}

_IMPORT_BODY: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "description": "A JSON list of FE-44 `Project` records.",
        "content": {"application/json": {"schema": {"type": "array", "items": {"type": "object"}}}},
    }
}


@router.get("/export/projects", response_class=Response, responses=_EXPORT_RESPONSES)
async def download_projects_export(
    db: Db,
    scope: Scope,
    reading: Reading,
    user: CurrentUser,
    file_format: Annotated[ExportFormat, Query(alias="format")],
    lang: PulseLanguage = PulseLanguage.PT_BR,
) -> Response:
    """The caller's projects as a file — reduced for everybody, headed, and logged.

    ``format`` is required: a file in a format nobody chose is a file nobody asked for. ``lang``
    is the header's and the column names' language; the cells are data in either. No cache may
    keep the answer — it is one caller's scope, headed for that caller — so it carries the
    collection's own :data:`~app.api.shema.projects.PER_READER_CACHE_CONTROL`.
    """
    exported = await export_projects(
        db,
        scope,
        readership=reading,
        user=user,
        file_format=file_format,
        language=lang,
        now=datetime.now(UTC).replace(microsecond=0),
    )
    return Response(
        content=exported.body.encode("utf-8"),
        media_type=exported.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{exported.filename}"',
            "Cache-Control": PER_READER_CACHE_CONTROL,
        },
    )


def _refused(refused: ImportRefused) -> JSONResponse:
    """The 400 the import dialog can explain itself with — its own key, and where.

    The repository's envelope, ``detail`` and ``code``, with the key beside it and the item or
    the id when the refusal has one. ``errors`` is Pydantic's list without the input, so the
    record is never echoed back.
    """
    content: dict[str, Any] = {
        "detail": str(refused),
        "code": ERROR_CODE_BAD_REQUEST,
        "key": refused.key.value,
    }
    if refused.index is not None:
        content["index"] = refused.index
    if refused.project_id is not None:
        content["id"] = refused.project_id
    if refused.errors:
        content["errors"] = refused.errors
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=content)


@router.post("/import/projects", response_model=ImportResult, openapi_extra=_IMPORT_BODY)
async def upload_projects_import(
    request: Request,
    db: Db,
    scope: Scope,
    reading: Reading,
    user: CurrentUser,
    local_day: Annotated[str | None, Header(alias=LOCAL_DAY_HEADER)] = None,
) -> ImportResult | JSONResponse:
    """Apply a list of records — all of them, or none — through the record's own write.

    The day progress entries are stamped with is the importer's, stated as a typed save states
    it (``projects.py``'s ``_local_day``). A record somebody saved while the file was being
    applied answers the record screen's own 409 (``projects.py``'s ``_conflict``) — who changed
    what, and when — with the item named in ``detail``; nothing of the file was applied.
    """
    today = datetime.now(UTC).date()
    try:
        return await import_projects(
            db,
            scope,
            await request.body(),
            readership=reading,
            user=user,
            day=_local_day(local_day, utc_today=today),
        )
    except ImportRefused as refused:
        return _refused(refused)
    except RecordVersionConflict as conflict:
        return _conflict(conflict)
