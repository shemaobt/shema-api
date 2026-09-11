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
and fails on a second one. The **rule** the first of them guards is not in this package
at all — it is inherited by every response model that leaves coordination, from
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

**BE-07 landed the health assessment**, and it is four files for the reasons above rather than
for a new one. ``append_assessment.py`` is the **only** writer of
``shema_health_assessments`` and the only thing that moves the record's seven flat health
fields, so *the projection is the newest entry* cannot be made false by a second writer;
``_health_audience.py`` is the sole owner of *who may read a reading of a team*, which is a
narrower question than who may open the record, and it answers it once for the read gate and
for the recipient list so the two cannot drift; ``_health_notice.py`` owns what a notice about a
struggling team may say, which is the part of that feature that actually needed deciding; and
``list_assessments.py`` is the history behind the narrower gate.

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
from app.services.shema._health_audience import (
    HEALTH_AUDIENCE,
    reads_assessments,
    recipients,
    require_reads_assessments,
)
from app.services.shema._health_notice import entered_critical, notice_body, notify_critical
from app.services.shema._media_sharing import (
    can_export_notes,
    can_share_media,
    is_authorized,
    recorded_decision,
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
from app.services.shema.append_assessment import append_assessment
from app.services.shema.browse_projects import browse_projects
from app.services.shema.count_projects import count_projects, count_projects_by_region
from app.services.shema.get_project import get_project
from app.services.shema.get_session import get_session
from app.services.shema.list_assessments import list_assessments
from app.services.shema.list_projects import list_projects
from app.services.shema.read_record import build_record, read_changes_since, read_record
from app.services.shema.save_project import RecordVersionConflict, create_project, save_project
from app.services.shema.set_region_scope import set_region_scope

__all__ = [
    "HEALTH_AUDIENCE",
    "Aggregates",
    "ChangesSince",
    "ProgressSource",
    "RecordVersionConflict",
    "RegionScope",
    "append_assessment",
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
    "entered_critical",
    "field_changes",
    "get_project",
    "get_session",
    "is_authorized",
    "is_withheld",
    "list_assessments",
    "list_projects",
    "log_reference",
    "notice_body",
    "notify_critical",
    "prayer_visibility",
    "reaches",
    "reaches_prayer_wall",
    "read_changes_since",
    "read_record",
    "reads_assessments",
    "recipients",
    "record_progress",
    "recorded_decision",
    "region_scope",
    "require_reads_assessments",
    "roll_up",
    "save_project",
    "searchable_text",
    "set_region_scope",
    "shared_prayer_audio",
    "shared_prayer_text",
    "visible_projects",
    "with_rolled_aggregates",
    "withheld_note",
    "within_scope",
]
