import asyncio
import base64
import hashlib

import google_crc32c
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.models.sound_necklace import ArtifactKind, AuditEvent, SnArtifact, SnSession
from app.services.oral_collector import gcs_utils
from app.services.sound_necklace.constants import (
    ARTIFACT_CONTENT_TYPES,
    ARTIFACT_FILENAMES,
    GCS_SN_BUCKET,
)
from app.services.sound_necklace.lock_fence import raise_if_locked_by_other
from app.services.sound_necklace.record_audit_event import record_audit_event


def _crc32c(data: bytes) -> str:
    return base64.b64encode(google_crc32c.Checksum(data).digest()).decode()


def _storage_key(session_id: str, kind: ArtifactKind, sha256: str) -> str:
    """Where one artifact's bytes live — an immutable, content-addressed path.

    The sha256 in the path is what makes a re-upload safe. A stable key (one per
    session+kind) would overwrite in place, and a failure partway through three
    overwrites would leave the bucket holding a triple that never coexisted while the
    database still described the old one. A content-addressed key never overwrites: a
    new upload writes a new object, the database pointer is what says which one is
    current, and a failed upload leaves an orphan nothing references rather than a
    corrupted current version.

    The frozen filename (PRD §10) is the last segment: a browser following the download
    redirect derives the saved name from the URL path, so the pipeline gets the name it
    expects without the API setting a header on bytes it never serves. The story slug is
    deliberately NOT in the key — it is user-controlled, and a slug like ``../..`` or one
    with a newline produces an object name that signs but 404s on fetch, a silent
    custody failure. The pretty download name, if ever wanted, belongs in the signed
    URL's response-disposition, not the object name.
    """
    return f"sound-necklace/{session_id}/{kind.value}/{sha256}/{ARTIFACT_FILENAMES[kind]}"


async def store_artifacts(
    db: AsyncSession, session: SnSession, payloads: dict[ArtifactKind, bytes], actor_user_id: str
) -> list[SnArtifact]:
    """Hand the three artifacts to storage exactly as they arrived, and record custody.

    The payloads arrive as bytes and stay bytes. **Nothing here parses one.** PRD §10.5
    makes that a contract breach and not a style preference: a parse-and-reserialize is
    invisible in review — the output is still valid, plausible JSON — and fatal to the
    pipeline, which diffs these files byte for byte against a golden reference.

    Fenced by the editor lock, before the bytes move and again before the pointers do.
    Raises ``SessionLockedByOther`` if somebody else holds the session.
    """
    session_id = session.id
    await raise_if_locked_by_other(db, session_id, actor_user_id)

    for kind, data in payloads.items():
        if not data:
            raise ValidationError(f"The {kind.value} artifact is empty")

    # Every object lands before any pointer moves. The three uploads are independent
    # network round trips, so they run concurrently rather than one waiting on the last.
    # Atomicity is unchanged: a failure in any of them raises out of the gather, no
    # pointer below is reached, get_db rolls the transaction back, and the session keeps
    # whatever triple it already had. The siblings of a failed upload are not cancelled
    # and may still land — content-addressed keys make those orphans nothing points at,
    # which is the same outcome the sequential version had.
    staged = []
    for kind, data in payloads.items():
        sha256 = hashlib.sha256(data).hexdigest()
        staged.append((kind, data, _storage_key(session_id, kind, sha256), sha256))

    await asyncio.gather(
        *(
            gcs_utils.upload_gcs_object(GCS_SN_BUCKET, key, data, ARTIFACT_CONTENT_TYPES[kind])
            for kind, data, key, _ in staged
        )
    )

    # Checked again, because the check above went stale while the bytes were in flight:
    # three round trips is long enough for a lease to lapse and be taken, after which the
    # pointers below would land on a session somebody else is now editing. This narrows
    # the window from the width of the upload to the width of the write — it does not
    # close it, and holding a row lock across the uploads to do so would trade an
    # advisory lock for a transaction pinned open on a network call. The objects already
    # sent are orphans nothing references; the pointers are what must not move.
    await raise_if_locked_by_other(db, session_id, actor_user_id)

    artifacts = []
    for kind, data, key, sha256 in staged:
        artifact = await db.get(SnArtifact, (session_id, kind))
        if artifact is None:
            artifact = SnArtifact(session_id=session_id, kind=kind)
            db.add(artifact)
        artifact.storage_key = key
        artifact.size = len(data)
        artifact.crc32c = _crc32c(data)
        artifact.sha256 = sha256
        artifact.content_type = ARTIFACT_CONTENT_TYPES[kind]
        artifacts.append(artifact)

    # One event for the triple, not three. The upload is atomic (§10.5) — a partial
    # triple is never stored — so three rows would describe three transfers that cannot
    # happen apart. This is the one audit point where the bytes really did pass through
    # the API, which is why it is the only name here that claims a transfer.
    #
    # The ref is derived from what was actually stored, in the same kind.value vocabulary
    # artifact_url_issued writes, sorted so the string is stable — not a hand-written
    # literal that could drift from the kinds or from that other event's words. The
    # download names one kind; the upload is the whole triple, so its ref is the join.
    uploaded_ref = ",".join(sorted(kind.value for kind in payloads))
    await record_audit_event(
        db,
        event=AuditEvent.ARTIFACT_UPLOADED,
        user_id=actor_user_id,
        project_id=session.project_id,
        resource_ref=uploaded_ref,
        session_id=session_id,
    )
    await db.commit()
    return artifacts
