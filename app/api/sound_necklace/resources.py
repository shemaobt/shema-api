"""Voice-answer resources (the canonical respostas/… paths).

Each answer is one WebM/Opus recording, uploaded straight to the API and served back
through a short-TTL signed URL. The bytes are opaque audio: the API only ever moves
them, never parses them. The path is validated against a fixed allowlist so it can be
trusted as the object-name suffix — no traversal, no free-form key.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.projects._deps import assert_project_access
from app.api.sound_necklace._deps import CurrentUser, Db
from app.models.sound_necklace import (
    RESOURCE_PATH_PATTERN,
    ResourceListResponse,
    ResourceSummary,
    ResourceUrlResponse,
)
from app.services import sound_necklace_service as sn_service
from app.services.sound_necklace.constants import MAX_VOICE_ANSWER_BYTES

router = APIRouter()

# One allowlist, one regex, whether the path arrives as a query param or names the
# uploaded object — validated the same way in every direction.
ResourcePath = Annotated[str, Query(pattern=RESOURCE_PATH_PATTERN)]


@router.put(
    "/sessions/{session_id}/resources",
    response_model=ResourceSummary,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {"description": "The answer is over the size cap"}
    },
)
async def put_resource(
    session_id: str, path: ResourcePath, request: Request, db: Db, user: CurrentUser
) -> ResourceSummary:
    """Upload a voice answer to a canonical path, replacing any previous take.

    The recording is read as raw bytes and moved to storage unchanged — it is opaque
    audio, so nothing parses it. The size is checked from the body before the upload, so
    an oversize answer never reaches the bucket.
    """
    session = await sn_service.get_session(db, session_id)
    await assert_project_access(db, user, session.project_id)

    data = await request.body()
    if len(data) > MAX_VOICE_ANSWER_BYTES:
        # A 413 is the honest status for a payload over the cap — distinct from the 422 a
        # malformed path gets, so a client can tell "too big" from "wrong path".
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="The voice answer is over the size cap",
        )

    answer = await sn_service.store_voice_answer(db, session_id, path, data)
    return ResourceSummary(path=answer.resource_path, size=answer.size)


@router.get("/sessions/{session_id}/resources", response_model=ResourceListResponse)
async def list_resources(session_id: str, db: Db, user: CurrentUser) -> ResourceListResponse:
    """List the session's recorded answers, so the screen knows which questions are done."""
    session = await sn_service.get_session(db, session_id)
    await assert_project_access(db, user, session.project_id)

    answers = await sn_service.list_voice_answers(db, session_id)
    return ResourceListResponse(
        resources=[ResourceSummary(path=a.resource_path, size=a.size) for a in answers]
    )


@router.get("/sessions/{session_id}/resources/url", response_model=ResourceUrlResponse)
async def resource_url(
    session_id: str, path: ResourcePath, db: Db, user: CurrentUser
) -> ResourceUrlResponse:
    """Mint a short-lived signed GET URL for one answer. The audit point (ENG-266)."""
    session = await sn_service.get_session(db, session_id)
    await assert_project_access(db, user, session.project_id)

    return ResourceUrlResponse(url=await sn_service.voice_answer_url(db, session, path, user.id))


@router.delete("/sessions/{session_id}/resources", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(session_id: str, path: ResourcePath, db: Db, user: CurrentUser) -> None:
    """Remove one answer — object and row. Deleting a path never recorded is a no-op."""
    session = await sn_service.get_session(db, session_id)
    await assert_project_access(db, user, session.project_id)

    await sn_service.delete_voice_answer(db, session_id, path)
