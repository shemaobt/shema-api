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

**BE-08 landed the needs and the money they carry.** ``_needs.py`` is the batch's own
rules, and it is a step of ``save_project`` rather than an endpoint because a need travels
with its project (``docs/shema.md`` §5.4) — one write path, one version guard, one
transaction, one trail, and an urgent need's notice staged under the same commit.
``list_unacknowledged_needs.py`` is the other half and the one the area exists for: *open,
and nobody has even looked*, as a single scoped query rather than as something somebody
remembers to check. Nothing in either sums a need: categories are not commensurable and
neither are currencies, and every amount is stored with the currency it is in.

**BE-06 landed the record's lifecycle**, and it is three files rather than one for the
reason the two above are one each. ``save_project.py`` is the **only** thing in this module
that moves ``shema_projects.version``, so the concurrency guard cannot be forgotten by a
second writer; ``_progress.py`` is the **only** writer of ``shema_progress_history``, which
is what makes an imported Pulse and a typed update indistinguishable afterwards (FE-44 §9.9);
and ``_audit.py`` is the only writer of the trail, which is what makes *who changed what* a
property of the write path rather than of whoever remembered. BE-07, BE-08 and BE-12 write
the record through ``save_project`` rather than beside it, and get all three.

``docs/shema.md`` §6 is why each is one file, and §3.3 is where every other concern
lands under the layering rules.
"""

from __future__ import annotations

from app.services.shema._audit import (
    ChangesSince,
    author_name,
    changes_since,
    field_changes,
)
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
    recorded_decision,
)
from app.services.shema._media_storage import (
    DOWNLOAD_URL_EXPIRY_MINUTES,
    GCS_SHEMA_BUCKET,
    storage_key,
)
from app.services.shema._needs import (
    NEEDS_FIELD_KEY,
    URGENT_NEED_EVENT,
    URGENT_NEED_ROLES,
    apply_needs,
    moves,
    notify_urgent,
    plan_needs,
    raise_day_moves,
)
from app.services.shema._progress import (
    Aggregates,
    ProgressSource,
    record_progress,
    roll_up,
    with_rolled_aggregates,
)
from app.services.shema._redaction import (
    derive_region,
    is_withheld,
    log_reference,
    searchable_text,
    withheld_note,
)
from app.services.shema._scope import (
    RegionScope,
    holders_reaching,
    reaches,
    region_scope,
    visible_projects,
    within_scope,
)
from app.services.shema.browse_projects import browse_projects
from app.services.shema.count_projects import count_projects, count_projects_by_region
from app.services.shema.get_project import get_project
from app.services.shema.get_session import get_session
from app.services.shema.list_projects import list_projects
from app.services.shema.list_unacknowledged_needs import (
    UNACKNOWLEDGED_AFTER_DAYS,
    list_unacknowledged_needs,
    unacknowledged_needs,
)
from app.services.shema.media_download_url import (
    MediaLink,
    material_download_url,
    media_download_url,
)
from app.services.shema.read_record import build_record, read_changes_since, read_record
from app.services.shema.save_project import RecordVersionConflict, create_project, save_project
from app.services.shema.set_region_scope import set_region_scope

__all__ = [
    "DOWNLOAD_URL_EXPIRY_MINUTES",
    "GCS_SHEMA_BUCKET",
    "NEEDS_FIELD_KEY",
    "UNACKNOWLEDGED_AFTER_DAYS",
    "URGENT_NEED_EVENT",
    "URGENT_NEED_ROLES",
    "Aggregates",
    "ChangesSince",
    "MediaLink",
    "ProgressSource",
    "RecordVersionConflict",
    "RegionScope",
    "apply_needs",
    "author_name",
    "browse_projects",
    "build_record",
    "can_export_notes",
    "can_share_media",
    "changes_since",
    "count_projects",
    "count_projects_by_region",
    "create_project",
    "derive_region",
    "field_changes",
    "get_project",
    "get_session",
    "holders_reaching",
    "is_authorized",
    "is_withheld",
    "list_projects",
    "list_unacknowledged_needs",
    "log_reference",
    "material_download_url",
    "media_download_url",
    "moves",
    "notify_urgent",
    "plan_needs",
    "prayer_visibility",
    "raise_day_moves",
    "reaches",
    "reaches_prayer_wall",
    "read_changes_since",
    "read_record",
    "record_progress",
    "recorded_decision",
    "region_scope",
    "roll_up",
    "save_project",
    "searchable_text",
    "set_region_scope",
    "shared_prayer_audio",
    "shared_prayer_text",
    "storage_key",
    "unacknowledged_needs",
    "visible_projects",
    "with_rolled_aggregates",
    "withheld_note",
    "within_scope",
]
