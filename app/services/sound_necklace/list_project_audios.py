from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AcoustemeStatus
from app.db.models.oc_acousteme import OC_AcoustemeArtifact
from app.db.models.sound_necklace import SnAudioRef
from app.models.sound_necklace import AcoustemeEnvelope, BucketAudioResponse
from app.services.oral_collector.acousteme_service import ACOUSTEME_GRANULARITY_FRAMES


def _resolve(artifacts: list[OC_AcoustemeArtifact]) -> OC_AcoustemeArtifact | None:
    """The artifact the play route will sign: newest READY, else newest of any status.

    This mirrors ``acousteme_service.get_artifact``, and it has to. The listing and
    ``/audios/{id}/url`` must resolve the *same* artifact, or the bucket describes one
    audio and plays another — a failed newer ingest would swap the story under the
    facilitator between the moment they read the title and the moment they press play.

    ``artifacts`` arrives newest-first.
    """
    ready = [a for a in artifacts if a.status == AcoustemeStatus.READY]
    for candidate in ready or artifacts:
        return candidate
    return None


def _envelope(artifact: OC_AcoustemeArtifact) -> AcoustemeEnvelope | None:
    """The grid, or nothing — never half of one.

    ``beadSec = granularity_frames[level] x hop_sec``, so an artifact without a hop is
    an artifact whose grid cannot be applied. The column is nullable and the DTO field
    is not: passing a null through would fail response validation and take the whole
    listing down with it, which is why this is a guard and not an assumption.

    A non-READY artifact has no stream behind it either. Both cases fall to the fixed
    durations of PRD §6.1 — the audio still lists, and still plays. It just has no grid.
    """
    if artifact.status != AcoustemeStatus.READY or artifact.hop_sec is None:
        return None
    return AcoustemeEnvelope(
        codebook_version=artifact.codebook_version,
        hop_sec=artifact.hop_sec,
        granularity_frames=dict(ACOUSTEME_GRANULARITY_FRAMES),
    )


async def list_project_audios(db: AsyncSession, project_id: str) -> list[BucketAudioResponse]:
    """The project's bucket audios, each with the grid its granularity is derived from.

    The acousteme table carries no project and no foreign key, so the join is on the
    convention that an audio ref's id is an artifact's ``audio_id``.

    Every audio listed here is one ``/audios/{id}/url`` can serve: the invariant is that
    the bucket never advertises what it cannot play. What varies is the envelope — an
    audio whose newest servable artifact is not READY lists with a null grid and falls
    back to fixed bead durations (PRD §6.1).
    """
    refs = (
        (
            await db.execute(
                select(SnAudioRef)
                .where(SnAudioRef.project_id == project_id)
                .order_by(SnAudioRef.audio_id)
            )
        )
        .scalars()
        .all()
    )
    if not refs:
        return []

    rows = (
        (
            await db.execute(
                select(OC_AcoustemeArtifact)
                .where(OC_AcoustemeArtifact.audio_id.in_([ref.audio_id for ref in refs]))
                # created_at is a transaction timestamp, so two versions ingested together
                # tie. The codebook is the tiebreak that keeps the winner deterministic.
                .order_by(
                    OC_AcoustemeArtifact.created_at.desc(),
                    OC_AcoustemeArtifact.codebook_version.desc(),
                )
            )
        )
        .scalars()
        .all()
    )

    by_audio: dict[str, list[OC_AcoustemeArtifact]] = {}
    for row in rows:
        by_audio.setdefault(row.audio_id, []).append(row)

    audios = []
    for ref in refs:
        artifact = _resolve(by_audio.get(ref.audio_id, []))
        # The bytes' location lives only on the acousteme row. An audio with no
        # artifact — or one that never recorded where its source went — has no known
        # bytes anywhere in the system. It is not an audio without a grid; it is an
        # audio that cannot be played, and a bucket must not offer a bead that 404s.
        if artifact is None or not artifact.audio_bucket or not artifact.audio_object:
            continue
        audios.append(
            BucketAudioResponse(
                id=ref.audio_id,
                filename=artifact.title or ref.audio_id,
                duration_sec=artifact.duration_sec,
                consent_present=ref.consent_present,
                acousteme=_envelope(artifact),
            )
        )
    return audios
