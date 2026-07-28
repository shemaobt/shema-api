"""Artifact custody.

The three artifacts are produced client-side and must survive byte-identical, so
they travel as raw multipart bytes on upload and are served straight from storage
on download — no Pydantic model ever parses a payload.
"""

from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.projects._deps import assert_project_access
from app.api.sound_necklace._deps import LOCKED_RESPONSE, CurrentUser, Db, locked_body
from app.models.sound_necklace import ArtifactKind, ArtifactResponse
from app.services import sound_necklace_service as sn_service

router = APIRouter()


@router.post(
    "/sessions/{session_id}/artifacts",
    response_model=list[ArtifactResponse],
    status_code=status.HTTP_201_CREATED,
    responses=LOCKED_RESPONSE,
)
async def upload_artifacts(
    session_id: str,
    db: Db,
    user: CurrentUser,
    manifest: UploadFile = File(),
    anchoring: UploadFile = File(),
    report: UploadFile = File(),
) -> list[ArtifactResponse] | JSONResponse:
    """Store the three artifacts as opaque bytes, checksummed on the way in.

    ``await file.read()`` is the whole of what happens to a payload here, and it has to
    stay that way. A JSON body would put the artifact through a parser, and a
    parsed-then-reserialized artifact is a broken one even while it still looks like
    perfectly valid JSON.
    """
    session = await sn_service.get_session(db, session_id)
    await assert_project_access(db, user, session.project_id)

    payloads = {
        ArtifactKind.MANIFEST: await manifest.read(),
        ArtifactKind.ANCHORING: await anchoring.read(),
        ArtifactKind.REPORT: await report.read(),
    }
    try:
        artifacts = await sn_service.store_artifacts(db, session, payloads, user.id)
    except sn_service.SessionLockedByOther as exc:
        return locked_body(exc)
    return [
        ArtifactResponse(kind=a.kind, size=a.size, crc32c=a.crc32c, sha256=a.sha256)
        for a in artifacts
    ]


@router.get(
    "/sessions/{session_id}/artifacts/{kind}",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    response_class=RedirectResponse,
    response_model=None,
)
async def download_artifact(
    session_id: str, kind: ArtifactKind, db: Db, user: CurrentUser
) -> RedirectResponse:
    """Redirect to a short-lived signed URL: storage serves the bytes verbatim.

    The API never proxies an artifact's bytes — that is what keeps the download
    byte-identical to the upload.
    """
    session = await sn_service.get_session(db, session_id)
    await assert_project_access(db, user, session.project_id)

    url = await sn_service.artifact_download_url(db, session, kind, user.id)
    return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
