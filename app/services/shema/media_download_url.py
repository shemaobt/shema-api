"""Hand out a file the way a private bucket allows: a short-lived signed GET, gated per call.

This is the half of FE-44 §8.3 that makes the other half mean something. ``can_share_media``
is a predicate, and a predicate that is consulted while the bytes sit behind a public URL
decides nothing — so the rule is applied **here**, on the call that produces the only address
the bytes have, and the address expires.

**Three gates, in the order they refuse**, and the order is the point:

1. ``get_project`` — the caller's region scope. A project outside it is 404, exactly as a
   project that does not exist is 404 (``_scope.py`` carries that argument).
2. the row exists and holds an object — a video is an address on somebody else's service and
   a photo slot may carry a caption and no image yet, so both are *nothing to serve*.
3. ``can_share_media`` — authorization, then audience, then the sensitive-country flag.

**The third refusal says nothing about which of its reasons fired.** An item nobody has
decided on, an item refused, and an authorized item on a withheld project asked for by a
public audience all answer the same sentence — because *the item is not shared with that
audience* is what the caller is entitled to know, and *why* is a fact about the project or
about a decision somebody made, which is the thing being protected. ``docs/shema.md`` §6.4's
line is that the retention is visible and says nothing about what.

**Storage serves the bytes; this API never proxies them**, which is the sibling's shape and
the reason the expiry is worth anything: there is no lasting link, because nothing stores one.

**Two collections, one implementation.** FE-44 §8.3 is *media and materials*, and the three
gates are the same three for both — so the two public names are three lines each over one
private helper. Two copies of this would be two chances for the second one to be written with
the audience gate in the wrong place, which is the defect this whole module is arranged
against.
"""

from __future__ import annotations

import logging
from typing import NamedTuple, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.db.models.auth import User
from app.db.models.shema_media import ShemaMaterial, ShemaMediaItem
from app.models.shema_privacy import ShemaAudience
from app.services.oral_collector import gcs_utils
from app.services.shema._media_sharing import can_share_media
from app.services.shema._media_storage import (
    DOWNLOAD_URL_EXPIRY_MINUTES,
    GCS_SHEMA_BUCKET,
)
from app.services.shema._redaction import log_reference
from app.services.shema._scope import RegionScope
from app.services.shema.get_project import get_project

logger = logging.getLogger(__name__)

#: One sentence for every way the third gate can refuse. See the module docstring.
NOT_SHARED = "This item is not shared with that audience"

#: The two tables that keep bytes behind a per-item decision. A constrained ``TypeVar`` and
#: not a shared base class: they are two tables with two lifecycles that happen to record the
#: same decision, and giving them a mapped parent to satisfy a type checker would put an
#: inheritance in the schema to express a fact about a function.
_Stored = TypeVar("_Stored", ShemaMediaItem, ShemaMaterial)


class MediaLink(NamedTuple):
    item: ShemaMediaItem | ShemaMaterial
    url: str
    expires_in_minutes: int


async def media_download_url(
    db: AsyncSession,
    scope: RegionScope,
    project_id: str,
    item_id: str,
    *,
    user: User,
    audience: ShemaAudience = ShemaAudience.COORDENACAO,
) -> MediaLink:
    """A signed URL for one photo, or a refusal that does not say which gate closed."""
    return await _link(
        db,
        scope,
        project_id,
        item_id,
        model=ShemaMediaItem,
        operation="media_download_url",
        user=user,
        audience=audience,
    )


async def material_download_url(
    db: AsyncSession,
    scope: RegionScope,
    project_id: str,
    material_id: str,
    *,
    user: User,
    audience: ShemaAudience = ShemaAudience.COORDENACAO,
) -> MediaLink:
    """The same three gates over what the project produced — text, audio or video."""
    return await _link(
        db,
        scope,
        project_id,
        material_id,
        model=ShemaMaterial,
        operation="material_download_url",
        user=user,
        audience=audience,
    )


async def _link(
    db: AsyncSession,
    scope: RegionScope,
    project_id: str,
    row_id: str,
    *,
    model: type[_Stored],
    operation: str,
    user: User,
    audience: ShemaAudience,
) -> MediaLink:
    """The three gates, once.

    **The default lives on the two public names and not here**, and it is ``coordenacao``,
    because the default that is safe to forget is the restrictive one: an authenticated
    console call gets it for free, while an export or a Pulse has to **write** ``publico``.
    Naming that audience is the act that should be deliberate. The reverse default would make
    *forgetting the argument* the way a file reaches the audience the product cannot take it
    back from.
    """
    project = await get_project(db, scope, project_id, user=user, operation=operation)

    stmt = select(model).where(model.project_id == project.id, model.id == row_id)
    item = (await db.execute(stmt)).scalar_one_or_none()
    if item is None or item.storage_key is None:
        raise NotFoundError("File not found")

    if not can_share_media(project, item, audience):
        logger.warning(
            "shema file refused: not shared with this audience",
            extra={
                "shema_operation": operation,
                "shema_user_id": user.id,
                "shema_item_id": item.id,
                "shema_audience": audience.value,
                **log_reference(project),
            },
        )
        raise AuthorizationError(NOT_SHARED)

    url = await gcs_utils.generate_signed_download_url(
        GCS_SHEMA_BUCKET,
        item.storage_key,
        expiry_minutes=DOWNLOAD_URL_EXPIRY_MINUTES,
    )
    return MediaLink(item=item, url=url, expires_in_minutes=DOWNLOAD_URL_EXPIRY_MINUTES)
