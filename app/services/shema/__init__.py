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

**BE-06 landed the record's lifecycle**, and it is three files rather than one for the
reason the two above are one each. ``save_project.py`` is the **only** thing in this module
that moves ``shema_projects.version``, so the concurrency guard cannot be forgotten by a
second writer; ``_progress.py`` is the **only** writer of ``shema_progress_history``, which
is what makes an imported Pulse and a typed update indistinguishable afterwards (FE-44 §9.9);
and ``_audit.py`` is the only writer of the trail, which is what makes *who changed what* a
property of the write path rather than of whoever remembered. BE-07, BE-08 and BE-12 write
the record through ``save_project`` rather than beside it, and get all three.

**BE-12 landed the forms and the leader link**, and the shape of it is one sentence: the
module's only unauthenticated seam deposits, and a signed-in coordinator applies.
``_intake_tokens.py`` is the whole guard — hash, expiry and revocation composed in
``verify_intake_token``, so a future caller inherits all three rather than the one it
remembered (``docs/shema.md`` §6.6); ``_form_definitions.py`` publishes the spec authored in
``app/utils/shema_forms.py`` as a **version that is cut and never edited**, because a
definition changed in place rewrites the meaning of every answer already given to it;
``_form_validation.py`` refuses a submission **whole**, naming every fault at once, before
anything is written anywhere; and ``import_submission.py`` writes the record through
``save_project`` with a ``ProgressSource``, which is BE-06's seam used rather than worked
around — an imported progress change and a typed one are one path, which is what makes them
indistinguishable afterwards.

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
from app.services.shema._form_definitions import (
    current_definition,
    definition_at,
    publish_definition,
)
from app.services.shema._form_validation import (
    record_update,
    validate_submission,
    validated_answers,
)
from app.services.shema._intake_tokens import (
    DEFAULT_LINK_DAYS,
    MAX_LINK_DAYS,
    expires_on,
    link_status,
    mint_token,
    verify_intake_token,
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
    reaches,
    region_scope,
    visible_projects,
    within_scope,
)
from app.services.shema._submission_archive import MAX_PAYLOAD_BYTES, archived_answers
from app.services.shema._submission_notices import notify_submission
from app.services.shema.browse_projects import browse_projects
from app.services.shema.count_projects import count_projects, count_projects_by_region
from app.services.shema.create_intake_link import create_intake_link
from app.services.shema.get_project import get_project
from app.services.shema.get_session import get_session
from app.services.shema.import_submission import apply_submission, import_submission
from app.services.shema.list_intake_links import list_intake_links
from app.services.shema.list_projects import list_projects
from app.services.shema.media_download_url import (
    MediaLink,
    material_download_url,
    media_download_url,
)
from app.services.shema.read_intake_form import form_fields, read_intake_form
from app.services.shema.read_record import build_record, read_changes_since, read_record
from app.services.shema.read_submission import as_received, list_submissions, read_submission
from app.services.shema.receive_submission import receive_submission
from app.services.shema.revoke_intake_link import revoke_intake_link
from app.services.shema.save_project import RecordVersionConflict, create_project, save_project
from app.services.shema.set_region_scope import set_region_scope

__all__ = [
    "DEFAULT_LINK_DAYS",
    "DOWNLOAD_URL_EXPIRY_MINUTES",
    "GCS_SHEMA_BUCKET",
    "MAX_LINK_DAYS",
    "MAX_PAYLOAD_BYTES",
    "Aggregates",
    "ChangesSince",
    "MediaLink",
    "ProgressSource",
    "RecordVersionConflict",
    "RegionScope",
    "apply_submission",
    "archived_answers",
    "as_received",
    "author_name",
    "browse_projects",
    "build_record",
    "can_export_notes",
    "can_share_media",
    "changes_since",
    "count_projects",
    "count_projects_by_region",
    "create_intake_link",
    "create_project",
    "current_definition",
    "definition_at",
    "derive_region",
    "expires_on",
    "field_changes",
    "form_fields",
    "get_project",
    "get_session",
    "import_submission",
    "is_authorized",
    "is_withheld",
    "link_status",
    "list_intake_links",
    "list_projects",
    "list_submissions",
    "log_reference",
    "material_download_url",
    "media_download_url",
    "mint_token",
    "notify_submission",
    "prayer_visibility",
    "publish_definition",
    "reaches",
    "reaches_prayer_wall",
    "read_changes_since",
    "read_intake_form",
    "read_record",
    "read_submission",
    "receive_submission",
    "record_progress",
    "record_update",
    "recorded_decision",
    "region_scope",
    "revoke_intake_link",
    "roll_up",
    "save_project",
    "searchable_text",
    "set_region_scope",
    "shared_prayer_audio",
    "shared_prayer_text",
    "storage_key",
    "validate_submission",
    "validated_answers",
    "verify_intake_token",
    "visible_projects",
    "with_rolled_aggregates",
    "withheld_note",
    "within_scope",
]
