"""Session lifecycle, autosave and resume.

The state document is the SPA's, not ours: it arrives as bytes, is stored as those
bytes, and is served back as those bytes. Nothing here parses it to persist it.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.projects._deps import assert_project_access
from app.api.sound_necklace._deps import LOCKED_RESPONSE, CurrentUser, Db, locked_body
from app.core.exceptions import ERROR_CODE_CONFLICT, ValidationError
from app.db.models.sound_necklace import SessionStatus, SessionStep, SnSession
from app.models.sound_necklace import (
    AutosaveResponse,
    ProjectGranularityLockedResponse,
    SessionCreate,
    SessionListResponse,
    SessionProgress,
    SessionStateUpdate,
    SessionSummary,
)
from app.services import sound_necklace_service as sn_service

router = APIRouter()

_CONFLICT_RESPONSE: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {
        "description": (
            "Refused. `code` says which guard refused it and what to do: CONFLICT means a "
            "newer version of the state exists and the body carries current_version — "
            "reload and retry. SESSION_LOCKED means somebody else holds the editor lock "
            "and the body carries holder_name and expires_at — stop writing and open in "
            "review mode."
        )
    }
}


_GRID_MISMATCH_RESPONSE: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {
        "model": ProjectGranularityLockedResponse,
        "description": (
            "The grid parameters do not agree with the project's. Nothing to retry: this "
            "audio cannot be cut on this project without splitting its corpus across two "
            "coordinate systems."
        ),
    }
}


def _summary(session: SnSession) -> SessionSummary:
    # A completed session shows the last station without overwriting where the state
    # was actually left, so a reopen lands back on the real one.
    step = SessionStep.SAVE if session.status is SessionStatus.COMPLETED else session.current_step
    return SessionSummary(
        id=session.id,
        project_id=session.project_id,
        story_name=session.story_name,
        story_slug=session.slug,
        status=session.status,
        last_modified=session.updated_at.isoformat(),
        progress=SessionProgress(current_step=step),
    )


def _etag(version: int) -> str:
    return f'"{version}"'


# The version column is a 32-bit int, so a larger number is not a version this API
# could have issued — and handing it to the driver as one is an error, not a miss.
_MAX_VERSION = 2**31 - 1


def _expected_version(if_match: str | None) -> int | None:
    """The state version the caller believes is current. Absent = unconditional write."""
    if if_match is None:
        return None
    try:
        version = int(if_match.strip().strip('"'))
    except ValueError:
        version = -1
    if not 0 <= version <= _MAX_VERSION:
        raise ValidationError("If-Match must carry a session-state version")
    return version


def _document(body: bytes) -> str:
    """The request body as text, to be stored as-is.

    `json.loads` accepts UTF-16 and UTF-32, so a body can satisfy the model and still
    not be UTF-8 — that is a bad request, not a server error.
    """
    try:
        return body.decode()
    except UnicodeDecodeError:
        raise ValidationError("The state document must be UTF-8 encoded JSON") from None


@router.post(
    "/sessions",
    response_model=SessionSummary,
    status_code=status.HTTP_201_CREATED,
    responses=_GRID_MISMATCH_RESPONSE,
)
async def create_session(payload: SessionCreate, db: Db, user: CurrentUser) -> SessionSummary:
    """Create a session from a bucket audio and grid parameters.

    The grid parameters are checked against the project's own before anything lands: a
    project cuts on one grid, and an audio whose acousteme resolves elsewhere is refused
    rather than cut on a second one.
    """
    await assert_project_access(db, user, payload.project_id)
    session = await sn_service.create_session(db, user, payload)
    return _summary(session)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    db: Db,
    user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> SessionListResponse:
    """List the caller's sessions with status and progress."""
    sessions = await sn_service.list_sessions(db, user, offset=offset, limit=limit)
    return SessionListResponse(sessions=[_summary(s) for s in sessions])


@router.get("/sessions/{session_id}", response_model=SessionSummary)
async def get_session(session_id: str, db: Db, user: CurrentUser) -> SessionSummary:
    """Fetch a single session for resume."""
    session = await sn_service.get_session(db, session_id)
    await assert_project_access(db, user, session.project_id)
    return _summary(session)


@router.get("/sessions/{session_id}/state", response_model=SessionStateUpdate)
async def get_session_state(session_id: str, db: Db, user: CurrentUser) -> Response:
    """The saved state document, served back as the exact bytes that were stored.

    Handed straight to the client rather than through a model, so nothing can
    re-shape a document the SPA will re-validate under a strict schema. ``ETag``
    carries the version to pass back in ``If-Match``.
    """
    session = await sn_service.get_session(db, session_id)
    await assert_project_access(db, user, session.project_id)
    document, version = await sn_service.load_state(db, session_id)
    return Response(
        content=document,
        media_type="application/json",
        headers={"ETag": _etag(version)},
    )


@router.put(
    "/sessions/{session_id}/state",
    response_model=AutosaveResponse,
    responses=_CONFLICT_RESPONSE,
)
async def autosave_session(
    session_id: str,
    payload: SessionStateUpdate,
    request: Request,
    response: Response,
    db: Db,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> AutosaveResponse | JSONResponse:
    """Autosave the session-state envelope with a version guard.

    ``payload`` validates the envelope; the raw request body is what gets stored.
    Sending ``If-Match`` makes the write conditional on that version still being
    current — without it the write is unconditional, which is what a single editor
    autosaving in a loop wants.
    """
    session = await sn_service.get_session(db, session_id)
    await assert_project_access(db, user, session.project_id)
    document = _document(await request.body())

    try:
        version, saved_at = await sn_service.autosave_state(
            db,
            session,
            document=document,
            # already parsed by the model; re-reading the raw text would reject bodies
            # the parser accepted (a UTF-8 BOM, for one)
            fields=payload.model_extra or {},
            expected_version=_expected_version(if_match),
            actor_user_id=user.id,
        )
    except sn_service.SessionLockedByOther as exc:
        return locked_body(exc)
    except sn_service.StateVersionConflict as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": str(exc),
                "code": ERROR_CODE_CONFLICT,
                "current_version": exc.current_version,
            },
        )

    response.headers["ETag"] = _etag(version)
    return AutosaveResponse(saved_at=saved_at.isoformat(), schema_version=payload.schema_version)


@router.post(
    "/sessions/{session_id}/complete",
    response_model=SessionSummary,
    responses=LOCKED_RESPONSE,
)
async def complete_session(
    session_id: str, db: Db, user: CurrentUser
) -> SessionSummary | JSONResponse:
    """Complete a session (its artifacts are uploaded to the artifacts route)."""
    session = await sn_service.get_session(db, session_id)
    await assert_project_access(db, user, session.project_id)
    try:
        completed = await sn_service.complete_session(db, session, user.id)
    except sn_service.SessionLockedByOther as exc:
        return locked_body(exc)
    return _summary(completed)


@router.post(
    "/sessions/{session_id}/reopen",
    response_model=SessionSummary,
    responses=LOCKED_RESPONSE,
)
async def reopen_session(
    session_id: str, db: Db, user: CurrentUser
) -> SessionSummary | JSONResponse:
    """Reopen a completed session."""
    session = await sn_service.get_session(db, session_id)
    await assert_project_access(db, user, session.project_id)
    try:
        reopened = await sn_service.reopen_session(db, session, user.id)
    except sn_service.SessionLockedByOther as exc:
        return locked_body(exc)
    return _summary(reopened)
