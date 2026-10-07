"""Who may read and write the Rhythm's log, and how far - the log's one rule, in one file.

Three services touch ``shema_meeting_log`` - the read, the write and the undo - and all three ask
the same two questions. Answering them here once is what keeps the read and the write from
drifting apart, which is ``_scope.py``'s argument for owning the region predicate, applied one
table over.

**The role: the health audience, and nobody wider.** The log's notes are what a meeting with a
field team produced - the general and emotional evaluation of the bimonthly meeting, the Member
Care debriefing - which is a pastoral reading of how a team is doing. ``_health_audience.py``
already answers *who follows up on a team*, and answered ``coordinator`` and ``obtLab``. The
list is **composed, not copied** - :func:`require_reads_meetings` asks ``files_assessments``,
the audience - so the day the client widens that audience, the log follows in the same edit.
OBT-571 widened the **reading** of a team's health to the Resource Circle and deliberately not
this log: the issue names the ficha, the card, the health tab, the filter and the order, and a
meeting's pastoral debriefing is none of them. Fail-closed: the ``resourceCircle`` role is
refused the log on all three routes, and so is any role a later issue adds.

**The region: the caller's scope, on both sides.** A regional caller reads and writes the
regions ``_scope.py`` says they reach, through its own ``reaches`` for the write and the same
set for the read; an empty regional scope reaches nothing. Out of scope is
:class:`~app.core.exceptions.AuthorizationError` and not a 404, because a region key is a public
vocabulary the console already holds - there is no existence to protect, the reasoning
``save_region_team.py`` gives for the same answer.

**``global`` has a path of its own, and it ends in a refusal with the reason.** ``scopeKey`` is a
``RegionKey`` or ``global`` in the frozen contract, and ``global`` belonged to the prototype's
annual celebration, which GATE-02 turned into a report. Every meeting of the set is held per
region, so a log under ``global`` is refused as a value
(:class:`~app.core.exceptions.UnprocessableValueError`) - the type accepts it precisely so the
answer can say why. On the read side no ``IN (regions)`` can match it, so only a global caller
would see such a row, and none can be written.
"""

from __future__ import annotations

import logging

from sqlalchemy import ColumnElement, false, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, UnprocessableValueError
from app.db.models.auth import User
from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_meeting import ShemaMeetingLogEntry
from app.services.shema._health_audience import HEALTH_AUDIENCE, files_assessments
from app.services.shema._scope import RegionScope, reaches
from app.utils.shema_meetings import GLOBAL_SCOPE_KEY, MeetingScopeKey

logger = logging.getLogger(__name__)


async def require_reads_meetings(
    db: AsyncSession, user: User, app_key: str, *, operation: str
) -> None:
    """Refuse an account outside the health audience - see the module docstring for why.

    A 403, as ``require_reads_assessments`` answers: the caller is being told about their own
    grant, which they already hold, so there is nothing an existence-hiding 404 would protect.
    """
    if await files_assessments(db, user, app_key):
        return
    logger.warning(
        "shema authorization refused: outside the audience of the rhythm's log",
        extra={
            "shema_operation": operation,
            "shema_user_id": user.id,
            "shema_audience": list(HEALTH_AUDIENCE),
        },
    )
    raise AuthorizationError(
        "The rhythm's log reaches the coordination, the OBT Lab and the global strategy; this "
        "account holds none of those roles in Shemá"
    )


def region_of(scope_key: MeetingScopeKey) -> ShemaRegionKey:
    """The region a log is written under, or the refusal of ``global`` with its reason."""
    if not isinstance(scope_key, ShemaRegionKey):
        raise UnprocessableValueError(
            f"scopeKey: '{GLOBAL_SCOPE_KEY}' is not a region, and every meeting of the rhythm is "
            "held per region"
        )
    return scope_key


def require_writes_region(scope: RegionScope, scope_key: MeetingScopeKey) -> ShemaRegionKey:
    """The region a write lands in, once the caller is known to reach it.

    ``global`` first, as a value, then the reach - so a global caller sending ``global`` is told
    the same thing as anyone else rather than being let through by the scope.
    """
    region = region_of(scope_key)
    if not reaches(scope, region):
        raise AuthorizationError("That region is outside your region scope")
    return region


def logs_within(scope: RegionScope) -> ColumnElement[bool]:
    """The read side of the same rule, as the ``WHERE`` every read of the log shares.

    A literal true for a global caller and a literal false for an empty regional scope, which is
    ``_scope.within_scope``'s shape for the same reason: a consumer composes it without branching,
    and the branch that is never written is the one that is never written wrong.
    """
    if scope.global_:
        return true()
    if not scope.regions:
        return false()
    return ShemaMeetingLogEntry.scope_key.in_(sorted(scope.regions))


async def find_log(
    db: AsyncSession, meeting_id: str, scope_key: str, period: str
) -> ShemaMeetingLogEntry | None:
    """The one row a ``(meeting, scope, period)`` can have, or ``None``."""
    stmt = select(ShemaMeetingLogEntry).where(
        ShemaMeetingLogEntry.meeting_id == meeting_id,
        ShemaMeetingLogEntry.scope_key == scope_key,
        ShemaMeetingLogEntry.period == period,
    )
    return (await db.execute(stmt)).scalar_one_or_none()
