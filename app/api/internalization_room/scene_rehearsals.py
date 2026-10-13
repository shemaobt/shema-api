"""The scene rehearsal's doors: the tablet keeps it, translates it and resumes it anywhere.

The tablet's doors carry no words of the team and no classifier guess (ENG-1335).
"""

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import device_dep, device_project_dep, linked_tablet_dep
from app.core.database import get_db
from app.db.models.internalization_room import IRSceneFrase, IRSceneRehearsal, IRSession
from app.models.internalization_room import (
    SceneFraseView,
    SceneRehearsalsResponse,
    SceneRehearsalView,
)
from app.services import internalization_room as room
from app.services.internalization_room import scene_rehearsals as scenes
from app.services.internalization_room.coverage import refuse_a_panorama
from app.services.internalization_room.takes import AUDIO_MIME, TakeStore, listen_url, take_store
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


def _view(rehearsal: IRSceneRehearsal, frases: list[IRSceneFrase]) -> SceneRehearsalView:
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
        recorded_at=as_utc(rehearsal.created_at).isoformat() if rehearsal.created_at else "",
        sent_at=as_utc(rehearsal.sent_at).isoformat() if rehearsal.sent_at else None,
        frases=[_frase_view(frase, replacing) for frase in frases],
    )


async def _the_record(db: AsyncSession, rehearsal: IRSceneRehearsal) -> SceneRehearsalView:
    frases = await scenes.frases_of(db, [rehearsal.id])
    return _view(rehearsal, frases[rehearsal.id])


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
    frases = await scenes.frases_of(db, [rehearsal.id for rehearsal in rehearsals])
    return SceneRehearsalsResponse(
        pericope=session.pericope,
        scene_rehearsals=[_view(rehearsal, frases[rehearsal.id]) for rehearsal in rehearsals],
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
        audio=await file.read(),
        content_type=file.content_type or AUDIO_MIME,
        filename=file.filename,
        store=store,
    )
    return await _the_record(db, rehearsal)
