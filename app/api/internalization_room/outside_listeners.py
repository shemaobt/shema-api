from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import ReaderUser
from app.api.internalization_room._deps import device_project_dep, linked_tablet_dep
from app.core.database import get_db
from app.db.models.internalization_room import IRExternalCheck
from app.models.internalization_room import (
    ExternalCheckListenersView,
    FinishRequest,
    ListenerFacts,
    ListenerFactsFrase,
    ListenerRecordingView,
    ListenerView,
    MarkRequest,
)
from app.services import internalization_room as room
from app.services.internalization_room.outside_listeners import (
    a_new_listener,
    finish_the_listener,
    keep_a_listener_recording,
    mark_the_frase_good,
    recording_view,
    the_check_of_version,
    the_listener,
    the_listeners_of,
)
from app.services.internalization_room.takes import LONGEST_TAKE_MS, TakeStore, take_store
from app.utils.stored_time import as_utc

router = APIRouter()

LISTENERS = "/sessions/{session_id}/external-check/{version}/listeners"


async def _the_teams_check(
    db: AsyncSession, session_id: str, version: int, project_id: str
) -> IRExternalCheck:
    session = await room.session_for_room_caller(db, session_id, project_id)
    return await the_check_of_version(db, session, version)


async def _as_it_stands(db: AsyncSession, check: IRExternalCheck, number: int) -> ListenerView:
    (listener,) = await the_listeners_of(db, check, number=number)
    return listener


@router.post(LISTENERS, response_model=ListenerView, dependencies=[linked_tablet_dep])
async def a_new_listener_route(
    session_id: str,
    version: int,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> ListenerView:
    """The team's tablet asks for the next **Outside listener** of this version's check.

    No body: the number is the room's to give, never the tablet's to send, and nothing names
    the person. 404 for a version whose check the team never opened.
    """
    check = await _the_teams_check(db, session_id, version, project_id)
    listener = await a_new_listener(db, check)
    return await _as_it_stands(db, check, listener.number)


@router.get(LISTENERS + "/{number}", response_model=ListenerFacts, dependencies=[linked_tablet_dep])
async def a_listeners_facts(
    session_id: str,
    version: int,
    number: int,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> ListenerFacts:
    """What the team reads back of a listener to resume one: facts, never a recording.

    How many of each recording were kept and on which frases, and the marks; no recording id,
    no fingerprint and no way to the audio, which only the facilitator's read reaches. 404 for
    an unknown listener or a version never opened.
    """
    check = await _the_teams_check(db, session_id, version, project_id)
    await the_listener(db, check, number)
    heard = await _as_it_stands(db, check, number)
    return ListenerFacts(
        number=heard.number,
        started_at=heard.started_at,
        finished_at=heard.finished_at,
        completed=heard.completed,
        retold=heard.retelling is not None,
        whole=len(heard.whole),
        frases=[
            ListenerFactsFrase(
                segment_id=frase.segment_id,
                frase=frase.frase,
                ok=frase.ok,
                comments=len(frase.comments),
            )
            for frase in heard.frases
        ],
    )


@router.post(
    LISTENERS + "/{number}/recordings",
    response_model=ListenerRecordingView,
    dependencies=[linked_tablet_dep],
    responses={
        422: {"description": "TAKE_FINGERPRINT_DIFFERS or TAKE_DURATION_DIFFERS: nothing kept"}
    },
)
async def keep_a_listener_recording_route(
    session_id: str,
    version: int,
    number: int,
    kind: str = Form(..., description="`retell`, `whole` or `frase`."),
    segment_id: str | None = Form(
        default=None,
        description=(
            "For a `frase` comment only: the frase's `segment_id` in the check, or a part's "
            "`take_id` on a check with no frases."
        ),
    ),
    duration_ms: int | None = Form(default=None, ge=0, le=LONGEST_TAKE_MS),
    sha256: str | None = Form(default=None),
    file: UploadFile = File(...),
    project_id: str = device_project_dep,
    store: TakeStore = Depends(take_store),
    db: AsyncSession = Depends(get_db),
) -> ListenerRecordingView:
    """A **Listener recording**, sent the moment it stops, as a take is sent.

    The bytes are in the bucket before the row names them, so a tab closed mid-way loses nothing
    already answered, and the same bytes sent again answer the recording already kept. No
    recognizer and no model is behind this door (the app's ADR 0111).

    400 for an unknown kind, a `frase` comment on no frase of this version or another kind
    naming one, or no audio; 422 for a fingerprint or length the bytes contradict; 404 for an
    unknown listener or a version never opened.
    """
    check = await _the_teams_check(db, session_id, version, project_id)
    listener = await the_listener(db, check, number)
    kept = await keep_a_listener_recording(
        db,
        check,
        listener,
        kind=kind,
        segment_id=segment_id,
        audio=await file.read(),
        content_type=file.content_type or "audio/mp4",
        sent_sha256=sha256,
        sent_duration_ms=duration_ms,
        store=store,
    )
    return recording_view(check, kept)


@router.post(
    LISTENERS + "/{number}/marks", response_model=ListenerView, dependencies=[linked_tablet_dep]
)
async def mark_the_frase_good_route(
    session_id: str,
    version: int,
    number: int,
    body: MarkRequest,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> ListenerView:
    """The listener says «está boa» on one frase; a comment on it, before or after, still
    makes it not ok. 400 for a frase not of this version, 404 as the other doors."""
    check = await _the_teams_check(db, session_id, version, project_id)
    listener = await the_listener(db, check, number)
    await mark_the_frase_good(db, check, listener, body.segment_id)
    return await _as_it_stands(db, check, number)


@router.post(
    LISTENERS + "/{number}/finish", response_model=ListenerView, dependencies=[linked_tablet_dep]
)
async def finish_the_listener_route(
    session_id: str,
    version: int,
    number: int,
    body: FinishRequest,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> ListenerView:
    """The listener is done: `completed` true when the last frase was answered, false after
    «terminar agora». The first finish is kept; a resend with another value changes nothing."""
    check = await _the_teams_check(db, session_id, version, project_id)
    await finish_the_listener(db, await the_listener(db, check, number), completed=body.completed)
    return await _as_it_stands(db, check, number)


@router.get(
    "/facilitator/sessions/{session_id}/external-check/{version}",
    response_model=ExternalCheckListenersView,
)
async def read_the_external_check_listeners(
    session_id: str, version: int, user: ReaderUser, db: AsyncSession = Depends(get_db)
) -> ExternalCheckListenersView:
    """A version's outside listeners with every recording they made, for the Desk and the
    export; an archived session's too (ADR 0052). No signed links: playing is the Desk's."""
    session = await room.get_session_for_reader(db, user, session_id)
    check = await the_check_of_version(db, session, version)
    return ExternalCheckListenersView(
        check_id=check.id,
        version=check.version,
        opened_at=as_utc(check.opened_at).isoformat(),
        listeners=await the_listeners_of(db, check),
    )
