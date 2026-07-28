from fastapi import APIRouter

from app.api.annotation_studio._deps import CurrentUser, Db
from app.services.annotation_studio import access, storage

router = APIRouter()


@router.get("/audio/url")
async def audio_url(key: str, db: Db, user: CurrentUser) -> dict[str, str]:
    """A short-lived signed GET URL for client-side playback of a stored object.

    The key must belong to an annotation-studio resource in a language the user
    can access — this blocks presigning arbitrary keys in the shared bucket.
    """
    language_id = await access.language_id_for_storage_key(db, key)
    await access.assert_language_access(db, user, language_id)
    return {"url": storage.presign_get(key)}
