"""The project's audio bucket, and the Sound Necklace's authenticated path to its bytes."""

from fastapi import APIRouter

from app.api.projects._deps import assert_project_access
from app.api.sound_necklace._deps import CurrentUser, Db
from app.models.sound_necklace import AudioUrlResponse, BucketAudioListResponse
from app.services import sound_necklace_service as sn_service

router = APIRouter()


@router.get("/projects/{project_id}/audios", response_model=BucketAudioListResponse)
async def list_project_audios(
    project_id: str, db: Db, user: CurrentUser
) -> BucketAudioListResponse:
    """List a project's story audios with their acousteme envelope and consent flag.

    Every audio listed is one the URL route below can serve. The bucket does not
    advertise a story it cannot play.
    """
    await assert_project_access(db, user, project_id)
    audios = await sn_service.list_project_audios(db, project_id)
    return BucketAudioListResponse(audios=audios)


@router.get("/audios/{audio_id}/url", response_model=AudioUrlResponse)
async def audio_signed_url(audio_id: str, db: Db, user: CurrentUser) -> AudioUrlResponse:
    """Mint a short-lived signed GET URL for audio playback.

    The bytes are never proxied and the bucket is private, so this is where the Sound
    Necklace reaches a recorded voice — and it is where ENG-266 will hook its audit log.

    It is the only route in this API that serves them — but only because ENG-290 made it
    so, and that is worth writing down rather than assuming. The Oral Collector's own
    acousteme routes minted the same signed URL for the same private object behind
    nothing but ``get_current_user`` — no app role, no project scoping — while the
    collection listing beside them handed over every id for free. For as long as those
    answered, the gate below narrowed nothing for anyone holding a Tripod account. They
    are retired. If they ever come back, this docstring is a lie again.
    """
    project_id = await sn_service.get_audio_project_id(db, audio_id)
    await assert_project_access(db, user, project_id)
    return AudioUrlResponse(
        url=await sn_service.audio_signed_url(
            db, audio_id, project_id=project_id, actor_user_id=user.id
        )
    )
