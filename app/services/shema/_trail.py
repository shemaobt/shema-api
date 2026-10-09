"""The change log's writer and the coverage rule — *every write to the PME leaves a mark*.

OBT-577. ``shema_record_edits`` (``_audit.py``) holds the project's fields with both sides of
each change. The writes that had no ledger of their own — an intercessor, a member, a meeting
log, a link — leave their mark here: **who, when, to what, and which keys**, in
``shema_change_log``. No value is written, so nothing in this table has to be withheld from a
reader afterwards.

**Staged, never committed.** :func:`stage` adds the row to the session and returns; the act's
own commit carries it. Services whose helper commits internally call :func:`stage` *before* the
helper, which is the same transaction: the row and the act are one write or neither, and a
refusal (a 404, a 403) rolls the row back with the session.

**The coverage is a registry, and a test walks the routes against it.** :data:`COVERAGE` names,
for every route of the module that is not a read, where its mark lands. ``TRAIL`` is this file's
table; ``LEDGER`` is a table that already records author and time for that act; ``EXEMPT`` is
a reason the act is not an alteration of the PME's data. A new write route with no entry fails
``tests/test_shema/test_change_log.py`` — the only way the rule *every write* stays true after
the person who wrote it has moved on.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Final, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema_change_log import ShemaChangeLog
from app.db.models.shema_enums import ShemaRegionKey
from app.services.shema._audit import author_name

_T = TypeVar("_T")

TRAIL: Final = "trail"
LEDGER: Final = "ledger"
EXEMPT: Final = "exempt"

#: The module's non-read routes, by endpoint function name → (kind, where / why).
COVERAGE: Final[dict[str, tuple[str, str]]] = {
    # --- the project record: shema_record_edits, with both sides of each field
    "patch_record": (LEDGER, "shema_record_edits"),
    "create_record": (LEDGER, "shema_record_edits"),
    "confirm": (LEDGER, "shema_record_edits"),
    "reject": (TRAIL, "pending project rejected"),
    "upload_projects_import": (LEDGER, "shema_record_edits: one entry per field the file moved"),
    "file_assessment": (LEDGER, "shema_health_assessments"),
    "withdraw_media_authorization": (TRAIL, "image authorization withdrawn"),
    # --- people
    "create_intercessor": (TRAIL, "intercessor created"),
    "edit_intercessor": (TRAIL, "intercessor edited"),
    "erase_intercessor": (TRAIL, "intercessor erased"),
    "mark_intercessor_reviewed": (TRAIL, "intercessor reviewed"),
    "grant_consent": (TRAIL, "consent recorded"),
    "revoke_consent": (TRAIL, "consent withdrawn"),
    "confirm_exit": (TRAIL, "left through an exit link; actor is the person"),
    "add_member": (LEDGER, "shema_project_members: added_by and added_at"),
    "remove_member": (LEDGER, "shema_project_members: removed_by and removed_at"),
    # --- the org chart and access
    "write_region_team": (LEDGER, "shema_role_changes"),
    "create_grant": (LEDGER, "shema_scope_changes and the platform's role grants"),
    "remove_grant": (LEDGER, "shema_scope_changes and the platform's role grants"),
    "create_invitation": (LEDGER, "access_invites: created_by and created_at"),
    "recall_invitation": (LEDGER, "access_invites: revoked_by and revoked_at"),
    # --- meetings, ETEN
    "write_meeting_log": (TRAIL, "meeting logged or replaced"),
    "remove_meeting_log": (TRAIL, "meeting log undone"),
    "put_eten_credit": (TRAIL, "ETEN credit recorded"),
    # --- the leader's door
    "mint_intake_link": (LEDGER, "shema_intake_links: created_by and created_at"),
    "revoke_link": (TRAIL, "intake link revoked"),
    "file_submission": (TRAIL, "submission filed by the coordination"),
    "import_received": (TRAIL, "submission imported"),
    "submit_intake_form": (LEDGER, "shema_submissions: the filing and its day"),
    "upload_intake_image": (LEDGER, "shema_intake_images: the upload and its day"),
    # --- the user's own state, not the PME's data
    "read_notifications_mark": (EXEMPT, "the reader's own read marks"),
    "write_notification_prefs": (EXEMPT, "the account's own notification preferences"),
}


def region_value(raw: object) -> str | None:
    """A region as the log stores it, or ``None`` for anything that is not one of the seven.

    A meeting's scope key can be ``global``; that act belongs to no region, and ``None`` is how
    the reader knows every reader of the log may be told of it.
    """
    value = str(getattr(raw, "value", raw))
    return value if value in {key.value for key in ShemaRegionKey} else None


def stage(
    db: AsyncSession,
    *,
    actor: User | None,
    subject: str,
    action: str,
    subject_id: str | None = None,
    project_id: str | None = None,
    region_key: str | None = None,
    fields: Iterable[str] = (),
    actor_name: str | None = None,
) -> ShemaChangeLog:
    """Add one row to the session for the act in hand.

    ``actor=None`` is an unauthenticated act, and ``actor_name`` then says who it was in words.
    """
    keys = sorted(set(fields))
    row = ShemaChangeLog(
        subject=subject,
        subject_id=subject_id,
        action=action,
        project_id=project_id,
        region_key=region_key,
        field_keys=json.dumps(keys) if keys else None,
        actor_id=None if actor is None else actor.id,
        actor_name=actor_name or author_name(actor),
    )
    db.add(row)
    return row


async def around(db: AsyncSession, act: Callable[[], Awaitable[_T]], **mark: Any) -> _T:
    """Stage the row, run ``act`` (whose commit carries it), and unstage it if ``act`` refuses.

    For an act whose helper both checks and commits — an intercessor by id that may be a 404 —
    so the row cannot outlive a refusal on a session that something else later commits. On a
    request's own session the rollback at close would have done it; the session a test, a
    script or a retry shares would not.
    """
    row = stage(db, **mark)
    try:
        return await act()
    except BaseException:
        if row in db:
            db.expunge(row)
        raise
