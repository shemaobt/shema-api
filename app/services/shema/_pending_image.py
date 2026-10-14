"""The Pulse's image **before** the import — where it is, and who may ask for its bytes (OBT-585).

``ShemaIntakeImage`` is the pointer the link's upload left; until a coordinator imports the
Pulse the photo is no media item, and ``docs/shema.md`` §6.6 says it is on no surface of the
**record**. This module is the one exception, and it is deliberately not the record: the inbox
detail says whether there is a pending image to ask for, and ``pending_image_download_url``
mints the fifteen-minute link — so the coordination can see the photograph on the screen where
it decides whether to import, which is the whole point of the inbox. The ficha, the card,
``hasMedia``, the export, the prayer wall and the Pulse keep not knowing the row exists.

**The two surfaces ask the same two functions**, so the flag the detail shows and the link the
route mints cannot disagree about who may ask — the flag is the link's four gates minus the
minting, which is what *there is something to ask for* has to mean.

The gates, in the order the link refuses them (the media item's, applied to a row that has no
decision yet):

1. the caller's scope — the submission is reached through ``scoped_submissions``, so a Pulse
   of a project outside it is not found, as the project itself would be;
2. an object to serve — the submission is still pending, its ``image`` answer names an upload,
   that upload is bound to **this** submission, and it holds a key. An imported Pulse is no
   longer pending: its photo is the record's, served by ``GET …/media/{item}/link`` under the
   decision the import recorded, which a withdrawal may since have reversed;
3. the leader's box — :func:`~app.services.shema._media_sharing.pulse_image_authorized`, the
   one reading the import also uses; unchecked or absent is undecided, refused;
4. the reader — :func:`~app.services.shema._media_sharing.reader_may_read_media`: on a withheld
   project the bytes are the coordination's only (Daniel, 9/oct/2026, option b), so the OBT Lab
   and the Resource Circle are refused here too, and the detail shows them no pending image —
   their ``answers`` are already ``{}`` and ``answersWithheld`` is already ``true`` (OBT-556).

Three and four answer the same sentence on the wire and different lines in the log, the
``media_download_url`` arrangement.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema import ShemaProject
from app.db.models.shema_form import ShemaIntakeImage, ShemaSubmission
from app.services.shema._media_sharing import pulse_image_authorized, reader_may_read_media
from app.services.shema._scope import Readership
from app.utils.shema_forms import IMAGE_FIELD


async def pending_image_of(
    db: AsyncSession, submission: ShemaSubmission, answers: Mapping[str, Any]
) -> ShemaIntakeImage | None:
    """Gate two: the upload this still-pending Pulse names, bound to it and holding a key."""
    if submission.applied_at is not None:
        return None
    image_id = answers.get(IMAGE_FIELD)
    if not isinstance(image_id, str) or not image_id:
        return None
    image = await db.get(ShemaIntakeImage, image_id)
    if image is None or image.submission_id != submission.id or not image.storage_key:
        return None
    return image


def may_read_pending_image(
    project: ShemaProject, answers: Mapping[str, Any], readership: Readership
) -> bool:
    """Gates three and four together — the box, then the reader."""
    return pulse_image_authorized(answers) and reader_may_read_media(
        project, readership.reader_of(project.region_key)
    )


async def pending_image_to_ask_for(
    db: AsyncSession,
    submission: ShemaSubmission,
    project: ShemaProject,
    answers: Mapping[str, Any],
    *,
    readership: Readership,
) -> bool:
    """What the inbox detail says: whether a call to the link would answer this reader a URL."""
    if not may_read_pending_image(project, answers, readership):
        return False
    return await pending_image_of(db, submission, answers) is not None
