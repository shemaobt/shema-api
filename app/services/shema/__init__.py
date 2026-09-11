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

**BE-07 landed the health assessment**, and it is four files for the reasons above rather than
for a new one. ``append_assessment.py`` is the **only** writer of
``shema_health_assessments`` and the only thing that moves the record's seven flat health
fields, so *the projection is the newest entry* cannot be made false by a second writer;
``_health_audience.py`` is the sole owner of *who may read a reading of a team*, which is a
narrower question than who may open the record, and it answers it once for the read gate and
for the recipient list so the two cannot drift; ``_health_notice.py`` owns what a notice about a
struggling team may say, which is the part of that feature that actually needed deciding; and
``list_assessments.py`` is the history behind the narrower gate.

**BE-15 landed the panel, the preferences and the read state** — the three things
``docs/shema.md`` §5.10 gives it, and none of them is a second delivery path. The panel is
``list_notification_panel.py``, which lists what BE-07, BE-08 and BE-12 already staged through
``create_notification`` for one recipient and adds the one kind with no discrete event —
staleness — computed fresh off ``browse_projects``'s own stale preset, already scoped and
already redacted. ``get_notification_prefs.py`` and ``save_notification_prefs.py`` are one
table's read and write, split for the reason every other pair in this module is; a channel
recorded there sends nothing, because no e-mail, push or WhatsApp sender exists anywhere in
``app/services/notifications/`` (§4.6). ``mark_notifications_read.py`` is the one write a mixed
batch of delivered and derived ids needs, and the only thing that ever writes
``shema_notification_reads``.

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
from app.services.shema._form_validation import record_update, validated_answers
from app.services.shema._health_audience import (
    HEALTH_AUDIENCE,
    reads_assessments,
    recipients,
    require_reads_assessments,
)
from app.services.shema._health_notice import entered_critical, notice_body, notify_critical
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
from app.services.shema._needs import (
    NEEDS_FIELD_KEY,
    URGENT_NEED_EVENT,
    URGENT_NEED_ROLES,
    Notice,
    apply_needs,
    notify_urgent,
    plan_needs,
    urgent_need_notice,
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
from app.services.shema._submission_archive import MAX_PAYLOAD_BYTES, archived_answers
from app.services.shema._submission_notices import notify_submission
from app.services.shema.append_assessment import append_assessment
from app.services.shema.browse_projects import browse_projects
from app.services.shema.count_projects import count_projects, count_projects_by_region
from app.services.shema.create_intake_link import create_intake_link
from app.services.shema.get_notification_prefs import get_notification_prefs
from app.services.shema.get_project import get_project
from app.services.shema.get_session import get_session
from app.services.shema.import_submission import apply_submission, import_submission
from app.services.shema.list_assessments import list_assessments
from app.services.shema.list_intake_links import list_intake_links
from app.services.shema.list_notification_panel import PANEL_CAP, list_notification_panel
from app.services.shema.list_projects import list_projects
from app.services.shema.list_unacknowledged_needs import (
    UNACKNOWLEDGED_AFTER_DAYS,
    list_unacknowledged_needs,
    unacknowledged_needs,
)
from app.services.shema.mark_notifications_read import mark_notifications_read
from app.services.shema.read_intake_form import form_fields, read_intake_form
from app.services.shema.read_record import build_record, read_changes_since, read_record
from app.services.shema.read_submission import as_received, list_submissions, read_submission
from app.services.shema.receive_submission import receive_submission
from app.services.shema.revoke_intake_link import revoke_intake_link
from app.services.shema.save_notification_prefs import save_notification_prefs
from app.services.shema.save_project import RecordVersionConflict, create_project, save_project
from app.services.shema.set_region_scope import set_region_scope

__all__ = [
    "DEFAULT_LINK_DAYS",
    "HEALTH_AUDIENCE",
    "MAX_LINK_DAYS",
    "MAX_PAYLOAD_BYTES",
    "NEEDS_FIELD_KEY",
    "PANEL_CAP",
    "UNACKNOWLEDGED_AFTER_DAYS",
    "URGENT_NEED_EVENT",
    "URGENT_NEED_ROLES",
    "Aggregates",
    "ChangesSince",
    "Notice",
    "ProgressSource",
    "RecordVersionConflict",
    "RegionScope",
    "append_assessment",
    "apply_needs",
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
    "entered_critical",
    "expires_on",
    "field_changes",
    "form_fields",
    "get_notification_prefs",
    "get_project",
    "get_session",
    "holders_reaching",
    "import_submission",
    "is_authorized",
    "is_withheld",
    "link_status",
    "list_assessments",
    "list_intake_links",
    "list_notification_panel",
    "list_projects",
    "list_submissions",
    "list_unacknowledged_needs",
    "log_reference",
    "mark_notifications_read",
    "mint_token",
    "notice_body",
    "notify_critical",
    "notify_submission",
    "notify_urgent",
    "plan_needs",
    "prayer_visibility",
    "publish_definition",
    "reaches",
    "reaches_prayer_wall",
    "read_changes_since",
    "read_intake_form",
    "read_record",
    "read_submission",
    "reads_assessments",
    "receive_submission",
    "recipients",
    "record_progress",
    "record_update",
    "recorded_decision",
    "region_scope",
    "require_reads_assessments",
    "revoke_intake_link",
    "roll_up",
    "save_notification_prefs",
    "save_project",
    "searchable_text",
    "set_region_scope",
    "shared_prayer_audio",
    "shared_prayer_text",
    "unacknowledged_needs",
    "urgent_need_notice",
    "validated_answers",
    "verify_intake_token",
    "visible_projects",
    "with_rolled_aggregates",
    "withheld_note",
    "within_scope",
]
