"""The scene rehearsal's doors: the tablet keeps it, translates it and resumes it anywhere.

The tablet's doors carry no words of the team and no classifier guess (ENG-1335); the reader
door is the facilitator's, and still reads a rehearsal its Zerar archived (ADR 0052).
"""

import uuid
from functools import partial

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import ReaderUser
from app.api.internalization_room._deps import device_dep, device_project_dep, linked_tablet_dep
from app.api.internalization_room.sessions import draft_the_turn
from app.core.config import get_settings
from app.core.database import get_db
from app.db.models.internalization_room import (
    IRSceneFrase,
    IRSceneRehearsal,
    IRSceneRestart,
    IRSession,
    IRSessionStatus,
)
from app.models.internalization_room import (
    HeldAttemptView,
    ReaderSceneFraseView,
    ReaderSceneRehearsalsResponse,
    ReaderSceneRehearsalView,
    SceneFraseView,
    SceneRehearsalsResponse,
    SceneRehearsalView,
    SceneRestartSnapshot,
    SceneRestartView,
    TurnResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room import scene_rehearsals as scenes
from app.services.internalization_room.coverage import refuse_a_panorama
from app.services.internalization_room.takes import AUDIO_MIME, TakeStore, listen_url, take_store
from app.services.internalization_room.turn_dedup import answer_once, answered_turn
from app.utils.stored_time import as_utc

router = APIRouter()


def _frase_view(frase: IRSceneFrase, replacing: dict[str, str]) -> SceneFraseView:
    return SceneFraseView(
        frase_id=frase.id,
        starts_ms=frase.starts_ms,
        ends_ms=frase.ends_ms,
        replaces=frase.replaces_id,
        replaced_by=replacing.get(frase.id),
    )


def _reader_frase_view(frase: IRSceneFrase, replacing: dict[str, str]) -> ReaderSceneFraseView:
    return ReaderSceneFraseView(
        frase_id=frase.id,
        starts_ms=frase.starts_ms,
        ends_ms=frase.ends_ms,
        replaces=frase.replaces_id,
        replaced_by=replacing.get(frase.id),
        transcript=frase.transcript,
    )


def _recorded_at(rehearsal: IRSceneRehearsal) -> str:
    return as_utc(rehearsal.created_at).isoformat() if rehearsal.created_at else ""


def _sent_at(rehearsal: IRSceneRehearsal, sent: set[str]) -> str | None:
    if rehearsal.sent_at is None or rehearsal.id not in sent:
        return None
    return as_utc(rehearsal.sent_at).isoformat()


def _view(
    rehearsal: IRSceneRehearsal,
    frases: list[IRSceneFrase],
    restarts: list[IRSceneRestart],
    sent: set[str],
) -> SceneRehearsalView:
    replacing = scenes.replaced_by(frases)
    return SceneRehearsalView(
        rehearsal_id=rehearsal.id,
        session_id=rehearsal.session_id,
        pericope=rehearsal.pericope,
        n=rehearsal.n,
        scene=rehearsal.scene,
        scene_said=rehearsal.scene_said.value if rehearsal.scene_said else None,
        duration_ms=rehearsal.duration_ms,
        content_type=rehearsal.content_type,
        verified=rehearsal.verified_at is not None,
        recorded_at=_recorded_at(rehearsal),
        sent_at=_sent_at(rehearsal, sent),
        after_restart=scenes.current_attempt(restarts),
        frases=[_frase_view(frase, replacing) for frase in frases],
    )


def _restart_view(restart: IRSceneRestart, set_aside: list[IRSceneFrase]) -> SceneRestartView:
    replacing = scenes.replaced_by(set_aside)
    return SceneRestartView(
        restart_id=restart.id,
        restarted_at=as_utc(restart.restarted_at).isoformat(),
        snapshot=SceneRestartSnapshot.model_validate(restart.snapshot),
        frases=[_reader_frase_view(frase, replacing) for frase in set_aside],
    )


def _reader_view(
    rehearsal: IRSceneRehearsal,
    frases: list[IRSceneFrase],
    restarts: list[IRSceneRestart],
    set_aside: dict[str, list[IRSceneFrase]],
    held: dict[str, list[IRSceneFrase]],
    sent: set[str],
) -> ReaderSceneRehearsalView:
    replacing = scenes.replaced_by(frases)
    return ReaderSceneRehearsalView(
        rehearsal_id=rehearsal.id,
        session_id=rehearsal.session_id,
        pericope=rehearsal.pericope,
        n=rehearsal.n,
        scene=rehearsal.scene,
        scene_said=rehearsal.scene_said.value if rehearsal.scene_said else None,
        duration_ms=rehearsal.duration_ms,
        content_type=rehearsal.content_type,
        verified=rehearsal.verified_at is not None,
        recorded_at=_recorded_at(rehearsal),
        sent_at=_sent_at(rehearsal, sent),
        after_restart=scenes.current_attempt(restarts),
        frases=[_reader_frase_view(frase, replacing) for frase in frases],
        scene_guess=rehearsal.scene_guess,
        archive_id=rehearsal.archive_id,
        restarts=[_restart_view(restart, set_aside.get(restart.id, [])) for restart in restarts],
        held=[
            HeldAttemptView(
                attempt=attempt,
                frases=[
                    _reader_frase_view(frase, scenes.replaced_by(waiting)) for frase in waiting
                ],
            )
            for attempt, waiting in held.items()
        ],
    )


async def _the_record(db: AsyncSession, rehearsal: IRSceneRehearsal) -> SceneRehearsalView:
    restarts = await scenes.restarts_of(db, [rehearsal.id])
    frases = await scenes.frases_of(db, restarts)
    sent = await scenes.sent_ones(db, [rehearsal])
    return _view(rehearsal, frases[rehearsal.id], restarts[rehearsal.id], sent)


async def _session(db: AsyncSession, session_id: str, project_id: str) -> IRSession:
    session = await room.session_for_room_caller(db, session_id, project_id)
    refuse_a_panorama(session.pericope)
    return session


@router.post(
    "/sessions/{session_id}/scene-rehearsals",
    response_model=SceneRehearsalView,
    dependencies=[linked_tablet_dep],
)
async def keep_scene_rehearsal(
    session_id: str,
    scene: str | None = Form(default=None),
    file: UploadFile = File(...),
    device_id: str = device_dep,
    project_id: str = device_project_dep,
    store: TakeStore = Depends(take_store),
    db: AsyncSession = Depends(get_db),
) -> SceneRehearsalView:
    session = await _session(db, session_id, project_id)
    rehearsal = await scenes.keep_scene_rehearsal(
        db,
        session,
        device_id=device_id,
        audio=await file.read(),
        content_type=file.content_type or AUDIO_MIME,
        scene=scene,
        store=store,
    )
    return await _the_record(db, rehearsal)


@router.get(
    "/sessions/{session_id}/scene-rehearsals",
    response_model=SceneRehearsalsResponse,
    dependencies=[linked_tablet_dep],
)
async def list_scene_rehearsals(
    session_id: str,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> SceneRehearsalsResponse:
    """The passage's live scene rehearsals, from every session of it, each naming its own."""
    session = await _session(db, session_id, project_id)
    rehearsals = await scenes.scene_rehearsals_of_the_passage(db, session)
    ids = [rehearsal.id for rehearsal in rehearsals]
    restarts = await scenes.restarts_of(db, ids)
    frases = await scenes.frases_of(db, restarts)
    sent = await scenes.sent_ones(db, rehearsals)
    return SceneRehearsalsResponse(
        pericope=session.pericope,
        scene_rehearsals=[
            _view(rehearsal, frases[rehearsal.id], restarts[rehearsal.id], sent)
            for rehearsal in rehearsals
        ],
    )


@router.get(
    "/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/audio",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    response_class=RedirectResponse,
    response_model=None,
    dependencies=[linked_tablet_dep],
)
async def listen_to_scene_rehearsal(
    session_id: str,
    rehearsal_id: str,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    session = await _session(db, session_id, project_id)
    rehearsal = await scenes.scene_rehearsal_in_session(db, session.id, rehearsal_id)
    await db.commit()
    return RedirectResponse(
        await listen_url(rehearsal), status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )


@router.get(
    "/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/frases/{frase_id}/audio",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    response_class=RedirectResponse,
    response_model=None,
    dependencies=[linked_tablet_dep],
)
async def listen_to_scene_frase(
    session_id: str,
    rehearsal_id: str,
    frase_id: str,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """A frase's own audio, any frase of the rehearsal, on any tablet of the team."""
    session = await _session(db, session_id, project_id)
    rehearsal = await scenes.scene_rehearsal_in_session(db, session.id, rehearsal_id)
    frase = await scenes.frase_in_rehearsal(db, rehearsal, frase_id)
    await db.commit()
    return RedirectResponse(await listen_url(frase), status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.post(
    "/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/frases",
    response_model=SceneRehearsalView,
    dependencies=[linked_tablet_dep],
)
async def keep_scene_frase(
    session_id: str,
    rehearsal_id: str,
    starts_ms: int = Form(...),
    ends_ms: int = Form(...),
    replaces: str | None = Form(default=None),
    after_restart: uuid.UUID | None = Form(default=None),
    file: UploadFile = File(...),
    project_id: str = device_project_dep,
    store: TakeStore = Depends(take_store),
    db: AsyncSession = Depends(get_db),
) -> SceneRehearsalView:
    session = await _session(db, session_id, project_id)
    rehearsal = await scenes.scene_rehearsal_in_session(db, session.id, rehearsal_id)
    await scenes.keep_a_frase(
        db,
        session,
        rehearsal,
        starts_ms=starts_ms,
        ends_ms=ends_ms,
        replaces=replaces,
        after_restart=None if after_restart is None else str(after_restart),
        audio=await file.read(),
        content_type=file.content_type or AUDIO_MIME,
        filename=file.filename,
        store=store,
    )
    return await _the_record(db, rehearsal)


@router.post(
    "/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/restart",
    response_model=SceneRehearsalView,
    dependencies=[linked_tablet_dep],
)
async def restart_scene_translation(
    session_id: str,
    rehearsal_id: str,
    attempt: uuid.UUID = Form(...),
    closes: uuid.UUID | None = Form(default=None),
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> SceneRehearsalView:
    """«recomeçar a tradução» into the attempt the tablet minted, whose id the outbox resends
    unchanged: the same restart sent twice is answered as the first. `closes` names the attempt
    it ends, the rehearsal's `after_restart` when the tablet restarted; a restart closing any
    other is refused with 409 and retried once its predecessor has landed."""
    session = await _session(db, session_id, project_id)
    rehearsal = await scenes.scene_rehearsal_in_session(db, session.id, rehearsal_id)
    await scenes.restart_the_scene_translation(
        db, rehearsal, attempt=str(attempt), closes=None if closes is None else str(closes)
    )
    return await _the_record(db, rehearsal)


@router.post(
    "/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/scene",
    response_model=SceneRehearsalView,
    dependencies=[linked_tablet_dep],
)
async def label_scene_rehearsal(
    session_id: str,
    rehearsal_id: str,
    scene: str = Form(...),
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> SceneRehearsalView:
    """A scene the passage lacks is refused with 422 `UNKNOWN_SCENE`."""
    session = await _session(db, session_id, project_id)
    rehearsal = await scenes.scene_rehearsal_in_session(db, session.id, rehearsal_id)
    labelled = await scenes.label_the_scene(db, rehearsal, scene)
    return await _the_record(db, labelled)


@router.post(
    "/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/send",
    response_model=TurnResponse,
    dependencies=[linked_tablet_dep],
)
async def send_scene_rehearsal(
    session_id: str,
    rehearsal_id: str,
    background: BackgroundTasks,
    turn_id: str = Form(..., max_length=64),
    closes: uuid.UUID | None = Form(default=None),
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> TurnResponse:
    """«terminei»: the scene's translation reaches the voice as a **Rehearsal turn**.

    The tablet sends the rehearsal by reference under a turn id it minted, naming the attempt it
    closes as a restart does (none before any restart). A resend under that turn id hears the
    first reply, read before the rehearsal is (ADR 0043); any other turn id is refused while
    another send stands (ADR 0063).
    """
    await db.commit()
    return await answer_once(
        session_id,
        turn_id,
        project_id,
        partial(
            _send,
            session_id=session_id,
            rehearsal_id=rehearsal_id,
            turn_id=turn_id,
            closes=None if closes is None else str(closes),
            project_id=project_id,
            background=background,
        ),
    )


async def _send(
    db: AsyncSession,
    *,
    session_id: str,
    rehearsal_id: str,
    turn_id: str,
    closes: str | None,
    project_id: str,
    background: BackgroundTasks,
) -> TurnResponse:
    replay = await answered_turn(db, session_id, turn_id, project_id)
    if replay is not None:
        return TurnResponse(**replay)
    session = await _session(db, session_id, project_id)
    rehearsal = await scenes.scene_rehearsal_in_session(db, session.id, rehearsal_id)
    bound_s = get_settings().internalization_room_turn_bound_ms / 1000
    return await scenes.send_the_scene_rehearsal(
        db,
        session,
        rehearsal,
        turn_id=turn_id,
        closes=closes,
        project_id=project_id,
        bound_s=bound_s,
        draft=partial(
            draft_the_turn,
            db,
            session,
            background=background,
            opening=False,
            halted=session.status is IRSessionStatus.NEEDS_PERSON,
            bound_s=bound_s,
        ),
    )


@router.get(
    "/facilitator/sessions/{session_id}/scene-rehearsals",
    response_model=ReaderSceneRehearsalsResponse,
)
async def facilitator_scene_rehearsals(
    session_id: str, user: ReaderUser, db: AsyncSession = Depends(get_db)
) -> ReaderSceneRehearsalsResponse:
    """The session's scene rehearsals with their words, restarts and guess, archived or not."""
    session = await room.get_session_for_reader(db, user, session_id)
    rehearsals = await scenes.scene_rehearsals_of_the_session(db, session.id)
    ids = [rehearsal.id for rehearsal in rehearsals]
    restarts = await scenes.restarts_of(db, ids)
    frases = await scenes.frases_of(db, restarts)
    set_aside = await scenes.set_aside_frases(db, ids)
    held = await scenes.held_frases(db, restarts)
    sent = await scenes.sent_ones(db, rehearsals)
    return ReaderSceneRehearsalsResponse(
        session_id=session.id,
        scene_rehearsals=[
            _reader_view(
                rehearsal,
                frases[rehearsal.id],
                restarts[rehearsal.id],
                set_aside,
                held[rehearsal.id],
                sent,
            )
            for rehearsal in rehearsals
        ],
    )
