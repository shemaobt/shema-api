"""Shemá's service layer — all of this module's logic and **all** of its queries.

One operation per file with a re-export here, which is the newer house style
(``app/services/access_request/``, ``project/``, ``auth/``, ``resource_request/``) rather
than the grouped ``*_service.py`` of ``annotation_studio/``.

**BE-03 landed the scope and the session.** ``_scope.py`` is the sole owner of the region
axis and of the module's only ``select(ShemaProject)``: every reader here starts from its
``visible_projects(scope)``, so a query that could return an out-of-scope row is not a
thing a later issue can write by forgetting something. The three query services beside it
— the collection, the record, the counts — exist as much to hold that property as to serve
an endpoint, because the issue's line is that such a query is a bug *even if no endpoint
calls it that way*. BE-05 and BE-06 build their endpoints on them rather than beside
them.

**BE-04 landed the three privacy owners**, and each is one file for the reason
``_scope.py`` is one file: a second reader of what it guards is the defect, not an
inconvenience. ``_redaction.py`` is the only reader of the sensitive-country columns,
``_consent.py`` the only reader of the three prayer columns, ``_media_sharing.py`` the
only reader of the three authorization columns, and
``tests/test_shema/test_privacy_owners.py`` globs this package and ``app/api/shema/``
and fails on a second one. ``_media_storage.py`` and ``media_download_url.py`` are the
fourth file and its one caller: a per-item authorization that ends in a public URL
enforces nothing, so the predicate is applied on the only address the bytes have and
that address expires (``docs/shema.md`` §4.6).

The **rule** the first of them guards is not in this package at all — it is inherited
by every response model that leaves coordination, from
``app/models/shema_privacy.py``, because ``app/models/`` may not import ``app/services/``
and because a rule a service has to call is a rule the next service forgets.

``docs/shema.md`` §6 is why each is one file, and §3.3 is where every other concern
lands under the layering rules.
"""

from __future__ import annotations

from app.services.shema._consent import (
    prayer_visibility,
    reaches_prayer_wall,
    shared_prayer_audio,
    shared_prayer_text,
)
from app.services.shema._media_sharing import (
    can_export_notes,
    can_share_media,
    is_authorized,
)
from app.services.shema._media_storage import (
    DOWNLOAD_URL_EXPIRY_MINUTES,
    GCS_SHEMA_BUCKET,
    storage_key,
)
from app.services.shema._redaction import (
    is_withheld,
    log_reference,
    searchable_text,
    withheld_note,
)
from app.services.shema._scope import (
    RegionScope,
    reaches,
    region_scope,
    visible_projects,
    within_scope,
)
from app.services.shema.count_projects import count_projects, count_projects_by_region
from app.services.shema.get_project import get_project
from app.services.shema.get_session import get_session
from app.services.shema.list_projects import list_projects
from app.services.shema.media_download_url import (
    MediaLink,
    material_download_url,
    media_download_url,
)
from app.services.shema.set_region_scope import set_region_scope

__all__ = [
    "DOWNLOAD_URL_EXPIRY_MINUTES",
    "GCS_SHEMA_BUCKET",
    "MediaLink",
    "RegionScope",
    "can_export_notes",
    "can_share_media",
    "count_projects",
    "count_projects_by_region",
    "get_project",
    "get_session",
    "is_authorized",
    "is_withheld",
    "list_projects",
    "log_reference",
    "material_download_url",
    "media_download_url",
    "prayer_visibility",
    "reaches",
    "reaches_prayer_wall",
    "region_scope",
    "searchable_text",
    "set_region_scope",
    "shared_prayer_audio",
    "shared_prayer_text",
    "storage_key",
    "visible_projects",
    "withheld_note",
    "within_scope",
]
