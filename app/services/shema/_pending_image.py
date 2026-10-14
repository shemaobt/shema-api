"""The Pulse's image **before** the import — where it is, and who may ask for its bytes (OBT-585).

``ShemaIntakeImage`` is the pointer the link's upload left; until a coordinator imports the
Pulse the photo is no media item, and ``docs/shema.md`` §6.6 says it is on no surface of the
**record**. This module is the one exception, and it is deliberately not the record: the inbox
detail says whether there is a pending image to ask for, and ``pending_image_download_url``
mints the fifteen-minute link — so the coordination can see the photograph on the screen where
it decides whether to import, which is the whole point of the inbox. The ficha, the card,
``hasMedia``, the export, the prayer wall and the Pulse keep not knowing the row exists.

**The two surfaces walk the same gates in the same order**, through :func:`pending_image_gates`,
so the flag the detail shows and the link the route mints cannot disagree about who may ask —
the flag is *the gates let this reader through*, which is what *there is something to ask for*
has to mean — and neither can reopen through the other what one of them closes.

The gates, in the order they refuse — and the order is **not** the media item's, on purpose:

1. the caller's scope — the submission is reached through ``scoped_submissions``, so a Pulse
   of a project outside it is not found, as the project itself would be;
2. **the reader, before the object** —
   :func:`~app.services.shema._media_sharing.reader_may_read_media`: on a withheld project
   the bytes are the coordination's only (Daniel, 9/oct/2026, option b),
   so the OBT Lab and the Resource Circle are refused here, **whatever the Pulse holds**. The
   item's link asks for the object first, and there it is harmless: the record already hands
   every reader the photo's ``id``. Here it would not be — the inbox detail hands the OBT Lab
   *no* answer of a withheld project (``answers`` ``{}``, ``answersWithheld``, OBT-556), and a
   404 for a Pulse without a photo beside a 403 for one with it would let that reader learn,
   submission by submission, which Pulses carry a photograph the detail hides (the Crivo's
   finding on this issue's first cut, 14/oct/2026). Refusing on the reader first makes the
   answer depend on the withheld bit and the role alone, and on nothing the reader may not know.
   The Resource Circle reads the answers (OBT-571) and had nothing to learn, and is refused all
   the same: one predicate, one order, for every reader;
3. an object to serve — the submission is still pending, its ``image`` answer names an upload,
   that upload is bound to **this** submission, and it holds a key. An imported Pulse is no
   longer pending: its photo is the record's, served by ``GET …/media/{item}/link`` under the
   decision the import recorded, which a withdrawal may since have reversed;
4. the leader's box — :func:`~app.services.shema._media_sharing.pulse_image_authorized`, the
   one reading the import also uses; unchecked or absent is undecided, refused.

Two and four answer the same sentence on the wire and different lines in the log, the
``media_download_url`` arrangement.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from typing import Any, NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema import ShemaProject
from app.db.models.shema_form import ShemaIntakeImage, ShemaSubmission
from app.models.shema_privacy import ShemaReader
from app.services.shema._media_sharing import pulse_image_authorized, reader_may_read_media
from app.services.shema._scope import Readership
from app.utils.shema_forms import IMAGE_FIELD


class PendingImageRefusal(enum.Enum):
    """Which gate closed — for the log, never for the wire."""

    READER = "reader"
    NO_OBJECT = "no_object"
    BOX = "box"


class PendingImageVerdict(NamedTuple):
    reader: ShemaReader
    image: ShemaIntakeImage | None
    refusal: PendingImageRefusal | None

    @property
    def readable(self) -> bool:
        return self.refusal is None


async def pending_image_of(
    db: AsyncSession, submission: ShemaSubmission, answers: Mapping[str, Any]
) -> ShemaIntakeImage | None:
    """Gate three: the upload this still-pending Pulse names, bound to it and holding a key."""
    if submission.applied_at is not None:
        return None
    image_id = answers.get(IMAGE_FIELD)
    if not isinstance(image_id, str) or not image_id:
        return None
    image = await db.get(ShemaIntakeImage, image_id)
    if image is None or image.submission_id != submission.id or not image.storage_key:
        return None
    return image


async def pending_image_gates(
    db: AsyncSession,
    submission: ShemaSubmission,
    project: ShemaProject,
    answers: Mapping[str, Any],
    *,
    readership: Readership,
) -> PendingImageVerdict:
    """Gates two to four, in that order, for a submission the scope has already let through."""
    reader = readership.reader_of(project.region_key)
    if not reader_may_read_media(project, reader):
        return PendingImageVerdict(reader, None, PendingImageRefusal.READER)
    image = await pending_image_of(db, submission, answers)
    if image is None:
        return PendingImageVerdict(reader, None, PendingImageRefusal.NO_OBJECT)
    if not pulse_image_authorized(answers):
        return PendingImageVerdict(reader, image, PendingImageRefusal.BOX)
    return PendingImageVerdict(reader, image, None)


async def pending_image_to_ask_for(
    db: AsyncSession,
    submission: ShemaSubmission,
    project: ShemaProject,
    answers: Mapping[str, Any],
    *,
    readership: Readership,
) -> bool:
    """What the inbox detail says: whether a call to the link would answer this reader a URL."""
    verdict = await pending_image_gates(db, submission, project, answers, readership=readership)
    return verdict.readable
