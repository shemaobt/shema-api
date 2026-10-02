"""A project notice is a row of ``notifications`` and the facts beside it (OBT-559).

The four writers of a project notice — ``_health_notice.py``, ``_needs.py`` and
``_submission_notices.py``'s two — used to write a sentence and nothing else, in English, into
the platform's ``title`` and ``body``; the PME's bell showed it as it came. The bell now words the
sentence in its reader's language, so each row is staged here with its
:class:`~app.db.models.shema_notification.ShemaProjectNotice`: the project, and what happened.
One function stages both, so a writer that calls it cannot stage the row without its facts —
the shape ``_request_notices._ring`` already has for the form's two notices.

**What happened, never who or where.** :class:`ProjectNoticeFacts` has no field for the
language's name, the region or the place: ``list_notification_panel.py`` reads each off the
project when the panel is read, through its owner, so a row cannot keep a name or a place past
the rule that withholds it. The English ``title`` and ``body`` are still written, for the readers
of ``notifications`` that are not the bell, and they name no place either.

``create_notification`` is called as it stands and with ``commit=False``: every writer stages
inside its caller's transaction, and whoever passes ``False`` owns the commit (``docs/shema.md``
§4.6).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema_notification import ShemaProjectNotice
from app.services.notifications.create_notification import create_notification


@dataclass(frozen=True)
class ProjectNoticeFacts:
    """The project a notice is about and the facts of its kind — nothing that names who or where.

    ``assessed_on`` is the health notice's; ``need_count``, ``need_categories`` and
    ``need_totals`` (one total per currency, never across them) the urgent needs'; ``submitted_by``
    the Pulse's. The prayer notice carries the project alone.
    """

    project_id: str
    assessed_on: date | None = None
    need_count: int | None = None
    need_categories: tuple[str, ...] | None = None
    need_totals: dict[str, Decimal] | None = None
    submitted_by: str | None = None


def _detail(notification_id: str, facts: ProjectNoticeFacts) -> ShemaProjectNotice:
    totals = (
        None
        if facts.need_totals is None
        else [
            {"amount": str(amount), "currency": currency}
            for currency, amount in sorted(facts.need_totals.items())
        ]
    )
    return ShemaProjectNotice(
        notification_id=notification_id,
        project_id=facts.project_id,
        assessed_on=facts.assessed_on,
        need_count=facts.need_count,
        need_categories=None if facts.need_categories is None else list(facts.need_categories),
        need_totals=totals,
        submitted_by=facts.submitted_by,
    )


async def stage_project_notice(
    db: AsyncSession,
    *,
    user_id: str,
    app_id: str,
    event_type: str,
    title: str,
    body: str,
    facts: ProjectNoticeFacts,
    actor_id: str | None = None,
) -> None:
    """Stage one notice and its facts for one recipient, inside the caller's transaction."""
    row = await create_notification(
        db,
        user_id=user_id,
        app_id=app_id,
        event_type=event_type,
        title=title,
        body=body,
        actor_id=actor_id,
        commit=False,
    )
    db.add(_detail(row.id, facts))
