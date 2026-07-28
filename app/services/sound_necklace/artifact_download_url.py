from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.sound_necklace import ArtifactKind, AuditEvent, SnArtifact, SnSession
from app.services.oral_collector import gcs_utils
from app.services.sound_necklace.constants import DOWNLOAD_URL_EXPIRY_MINUTES, GCS_SN_BUCKET
from app.services.sound_necklace.record_audit_event import record_audit_event


async def artifact_download_url(
    db: AsyncSession, session: SnSession, kind: ArtifactKind, actor_user_id: str
) -> str:
    """A short-lived signed GET for one artifact.

    Storage serves the bytes; the API never proxies them — which is exactly what keeps
    the download byte-identical to the upload. A proxy would have to choose an encoding,
    and any choice is a chance to be wrong.

    The issuance is recorded (§12) and the commit is what returns the URL, so nothing
    hands out a signed link without a row naming who got it. Takes the session rather than
    its id because the log is queryable per project and the project is on it — the same
    reason ``complete_session`` takes one.
    """
    artifact = await db.get(SnArtifact, (session.id, kind))
    if artifact is None:
        raise NotFoundError(f"No {kind.value} artifact for this session")

    url = await gcs_utils.generate_signed_download_url(
        GCS_SN_BUCKET,
        artifact.storage_key,
        expiry_minutes=DOWNLOAD_URL_EXPIRY_MINUTES,
    )
    # The kind, not the storage key: the key is content-addressed, so a re-upload moves it
    # and a stored key would later read as a file this download never served. The artifact
    # is keyed (session, kind) anyway — that pair is its identity.
    await record_audit_event(
        db,
        event=AuditEvent.ARTIFACT_URL_ISSUED,
        user_id=actor_user_id,
        project_id=session.project_id,
        resource_ref=kind.value,
        session_id=session.id,
    )
    await db.commit()
    return url
