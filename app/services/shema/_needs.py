"""The needs half of the record's write, and the notice an urgent one sends.

**A need is a request for help and it has a life.** Raised, seen, being attended, attended —
and the one this area exists to prevent is the first of those lasting a year because nobody
ever got as far as the second. So the states are stored, the acknowledgement is stored beside
them, and ``list_unacknowledged_needs`` is one query over both. What is *not* here is a
number: needs are not summed, because a category is not commensurable with another category
and a currency is not commensurable with another currency.

**Needs travel with the project** (``docs/shema.md`` §5.4, FE-44 §9.5), so this is a step of
``save_project`` and not an endpoint: one write path, one version guard, one transaction, one
trail. Giving ``needsItems`` a second owner is the thing that section refuses, and a second
endpoint is exactly how it would get one.

**The batch is an upsert and never a replacement, and that is a decision.** A need present in
``needsItems`` is created or moved; a need **absent** from it is untouched. Two reasons agree.
``app/models/shema.py``'s own rule is *absent means unchanged, all the way down* — a tab sends
what it owns — and reading an omission as a delete would make one field of the record behave
opposite to the other seventy-two. And the aggregate's own invariant says the same thing from
the other side: ``dropped`` exists so that a request that stopped mattering leaves the open
list **without being deleted**, because deleting loses the history a region is judged by. So
nothing here deletes a need, and the product's answer to *take this off my list* is the state
it already has.

**The order, inside** ``save_project``'s **one transaction**: the whole batch is resolved and
validated before a single row is touched — an unknown id names itself and nothing at all is
written — then the rows move, then the trail, then the notices, then the caller's one commit.
``create_notification(..., commit=False)`` is what puts the notice inside that transaction, as
its own docstring asks: a save that landed always carries its notices, and a save that rolled
back leaves none.

**The app key comes from** ``app/services/notifications/get_shema_app_id.py`` **and is not
retyped here.** ``app/api/shema/_deps.py`` is where *the module* names it and a test keeps it
named once there; the notifications package serves eight applications and each of them resolves
its own key and id in that package, which is the sibling's shape
(``get_rr_app_id.py``/``_deps.py``, with a test asserting the two agree). This module's copy of
that test is ``tests/test_shema/test_needs.py``.

**This file names no guarded column.** It reads the project's ``region_key`` to address a
notice and its ``language_name`` to word one; the place, the base and the contacts it never
touches, because the body of a notice is built by validating
:class:`~app.models.shema_need.ShemaNeedLine` off the row — a
:class:`~app.models.shema_privacy.LeavingShape`, which reduces them by the act of declaring
them. That is the same trade the whole module makes: the rule is inherited, not called.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaNeedUrgency
from app.db.models.shema_need import ShemaNeed
from app.models.shema_need import ShemaNeedLine, ShemaNeedWrite, is_still_open
from app.services import authorization_service
from app.services.notifications import create_notification, get_shema_app_id
from app.services.notifications.get_shema_app_id import SHEMA_APP_KEY
from app.services.shema import _audit
from app.services.shema._scope import COORDINATOR_ROLE, OBT_LAB_ROLE, holders_reaching

logger = logging.getLogger(__name__)

#: What ``notifications.event_type`` carries for this notice. Dotted and namespaced by the
#: module, so a panel that lists eight applications' rows can tell whose it is without joining
#: ``apps``; FE-44 §5.8's ``AppNotification.kind`` is ``need``, and this is the transport's
#: spelling of the same fact.
URGENT_NEED_EVENT = "shema.need.urgent"

#: The wire key a needs change is recorded under in the edit trail, and the key a 409's
#: ``changedFields`` carries. One key for the whole collection rather than one per need: the
#: console looks it up where it looks up its labels, and *the needs moved* is the sentence a
#: coordinator acts on.
NEEDS_FIELD_KEY = "needsItems"

#: Who an urgent need reaches — FE-44 §5.8's routing, verbatim: *health, need and stale reach*
#: ``coordinator`` *and* ``obtLab``; prayer reaches ``resourceCircle`` alone. Named here beside
#: the one notice this module sends rather than in a table, because there is one notice.
URGENT_NEED_ROLES = (COORDINATOR_ROLE, OBT_LAB_ROLE)

#: The columns a batch row may move. ``id`` addresses, ``acknowledged`` is a gesture the server
#: turns into three columns, and everything else is a value copied across.
_WRITTEN_COLUMNS = (
    "category",
    "urgency",
    "status",
    "description",
    "estimated_value",
    "estimated_amount",
    "estimated_currency",
    "deadline",
    "prayer_shared",
    "prayer_answered",
    "fulfilled_by",
    "fulfilled_date",
    "dropped_date",
    "submitted_by",
    "submitted_at",
)

#: What the trail records about a need that moved. The lifecycle and nothing else: the
#: description is free text a team wrote and could name a place, and ``_audit.py``'s own rule
#: is that a trail is read by more people and kept longer than a response body. A reader learns
#: that the need moved and goes to the record, where being allowed is checked.
_TRAIL_COLUMNS = ("category", "urgency", "status", "acknowledged_at")


class Notice(NamedTuple):
    """One notification's two strings, rendered before anything is written.

    A shape rather than a tuple of two strings, so the caller cannot swap them: a title in a
    body renders, and nothing fails.
    """

    title: str
    body: str


def urgent_need_notice(line: ShemaNeedLine) -> Notice:
    """What an urgent need says to the people it reaches.

    **Built from the leaving shape and from nothing else**, which is what makes it safe
    without anybody here knowing the privacy rule: ``line.location`` is already the region key
    for a flagged project, and there is no ``project.location`` in this function to leak. The
    description is deliberately absent — it is free text a team wrote about their own
    situation, and a notice is not the surface to forward it on.

    The amount is in the body when there is one, because for an urgent need it is the fact the
    recipient acts on, and it carries its currency because in this module a number never
    travels without one.

    **The copy is English**, which is a pendency rather than a decision: every notification
    title in this repository is English, and the product's bilingual client-facing copy is
    still open. Writing invented Portuguese here would put unapproved wording in front of a
    field team on nobody's authority — the sibling's ``_notices.py`` says the same and for the
    same reason.
    """
    who = line.language_name or line.project_id
    where = f" ({line.location})" if line.location else ""
    money = (
        ""
        if line.estimated_amount is None
        else f" Estimated at {line.estimated_amount} {line.estimated_currency}."
    )
    return Notice(
        title=f"Urgent need: {line.category}",
        body=f"{who}{where} raised an urgent {line.category} need.{money}",
    )


def urgent_needs_notice(lines: list[ShemaNeedLine]) -> Notice:
    """What **one save's** urgent needs say to the people they reach, in one notice.

    **A batch is one notice per recipient, never one per need per recipient.** A save that
    imports twenty rows and turns five of them urgent is one event a coordinator can act on,
    not five interruptions telling the same story — BE-15's own line in ``docs/shema.md``'s
    delivery plan is that an import which floods a panel trains its reader to stop opening it,
    which is a worse failure than the notice never having existed. :func:`urgent_need_notice`
    still answers the single-need case, unchanged, because most saves raise one.

    Amounts are summed **per currency, never across one**, for the reason this module never
    sums a need: a rupiah total beside a real total invents a number nobody asked for. A
    currency with no amount for every need in the batch is left out rather than shown as zero.
    """
    if len(lines) == 1:
        return urgent_need_notice(lines[0])

    who = lines[0].language_name or lines[0].project_id
    where = f" ({lines[0].location})" if lines[0].location else ""
    categories = ", ".join(sorted({line.category for line in lines}))

    totals: dict[str, Decimal] = {}
    for line in lines:
        if line.estimated_amount is not None and line.estimated_currency:
            totals[line.estimated_currency] = (
                totals.get(line.estimated_currency, Decimal(0)) + line.estimated_amount
            )
    money = (
        ""
        if not totals
        else " Estimated at "
        + ", ".join(f"{amount} {currency}" for currency, amount in sorted(totals.items()))
        + "."
    )

    return Notice(
        title=f"{len(lines)} urgent needs raised",
        body=f"{who}{where} raised {len(lines)} urgent needs: {categories}.{money}",
    )


def _lifecycle(need: ShemaNeed) -> str:
    """One need's lifecycle, as the trail stores a side of a change.

    ``default=str`` renders the one date among them; an enum renders as its value, which is
    the spelling FE-44 froze and the one a reader of the trail recognises.
    """
    state: dict[str, Any] = {"id": need.id}
    for column in _TRAIL_COLUMNS:
        value = getattr(need, column)
        state[column] = value.value if hasattr(value, "value") else value
    return json.dumps(state, ensure_ascii=False, default=str)


@dataclass
class NeedPlan:
    """Every row this batch will touch, resolved and validated, with nothing applied yet.

    Built before the write for the reason ``save_project``'s own ``_merged`` is: *a partial
    failure applies nothing* becomes a property of the order rather than of a rollback, and a
    function that mutates and then checks is one early ``return`` away from being wrong.
    """

    creates: list[ShemaNeedWrite] = field(default_factory=list)
    updates: list[tuple[ShemaNeed, ShemaNeedWrite]] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.creates or self.updates)


async def plan_needs(
    db: AsyncSession, project: ShemaProject, rows: list[ShemaNeedWrite]
) -> NeedPlan:
    """Resolve a batch against the project's own needs, naming every bad row at once.

    **Every bad row at once, located by index**, which is the rule the record's progress batch
    already follows: a client fixing one id at a time learns one problem per round trip, and a
    batch that reported only its first failure would make a ten-row tab a ten-request
    conversation.

    An id that belongs to **another** project is refused exactly as an unknown one is. It is
    not an oracle — the caller already reached this project through the scope — and answering
    *that id is somebody else's* would say that the id exists.
    """
    existing = {
        row.id: row
        for row in (
            await db.execute(select(ShemaNeed).where(ShemaNeed.project_id == project.id))
        ).scalars()
    }

    plan, unknown = NeedPlan(), []
    for index, row in enumerate(rows):
        if row.id is None:
            plan.creates.append(row)
        elif row.id in existing:
            plan.updates.append((existing[row.id], row))
        else:
            unknown.append(f"needsItems[{index}]: {row.id} is not a need of this project")
    if unknown:
        raise ValidationError("; ".join(unknown))
    return plan


def _acknowledge(need: ShemaNeed, *, user: User | None, day: date) -> None:
    """Stamp *somebody has seen this*, once.

    **Never re-stamped and never cleared.** The first acknowledgement is the one that answers
    the question the column exists for — *how long did this sit before anybody looked* — so a
    later save by a second person does not move the date, and a payload that sends the gesture
    as ``false`` takes nothing back. Un-seeing is not a gesture the product has.
    """
    if need.acknowledged_at is not None:
        return
    need.acknowledged_at = day
    need.acknowledged_by = None if user is None else user.id
    need.acknowledged_by_name = _audit.author_name(user)


def _apply(need: ShemaNeed, row: ShemaNeedWrite, *, user: User | None, day: date) -> bool:
    """Move one row onto one need; answer whether anything actually changed.

    Equality and not identity, for ``_audit.py``'s reason: a tab re-sending a need it did not
    touch is not an edit, and a version bump on it would refuse every other coordinator in the
    meeting over a save that moved nothing.
    """
    moved = False
    for column in _WRITTEN_COLUMNS:
        value = getattr(row, column)
        if getattr(need, column) != value:
            setattr(need, column, value)
            moved = True
    if row.acknowledged and need.acknowledged_at is None:
        _acknowledge(need, user=user, day=day)
        moved = True
    return moved


def _new_need(project_id: str, row: ShemaNeedWrite, *, user: User | None, day: date) -> ShemaNeed:
    """One need, as the batch asked for it.

    ``submitted_at`` falls back to the day it was raised rather than staying NULL, and that is
    the one value this path supplies that the payload did not. Two things depend on the column
    being answerable: the sweep measures a need's age from it, and FE-44 §5.8 keys a derived
    notification on ``need:{project}:{category}:{submittedAt}`` — an id with a hole in it is
    not stable, and a need with no date is a need no threshold can be past.
    """
    need = ShemaNeed(
        project_id=project_id,
        **{column: getattr(row, column) for column in _WRITTEN_COLUMNS},
    )
    if need.submitted_at is None:
        need.submitted_at = day
    if row.acknowledged:
        _acknowledge(need, user=user, day=day)
    return need


def _is_urgent_and_open(need: ShemaNeed) -> bool:
    """Whether this need is the thing somebody has to be told about now."""
    return need.urgency is ShemaNeedUrgency.HIGH and is_still_open(need.status)


async def apply_needs(
    db: AsyncSession,
    project: ShemaProject,
    plan: NeedPlan,
    *,
    user: User | None,
    day: date,
) -> tuple[list[_audit.FieldChange], list[ShemaNeed]]:
    """Write the batch; answer the trail rows it earned and the needs that became urgent.

    Staged and never committed — the caller owns the transaction, which is what makes the
    record, the needs, the trail and the notices one write. ``_audit.py``'s contract, for its
    reason: a trail written under its own commit is a trail that can outlive a save that did
    not happen.

    **A need becomes urgent by entering the state, not by being in it.** A save that re-sends
    an already-urgent, already-open need sends no second notice; one that raises a medium need
    to ``high``, or reopens an urgent one, does. That is what keeps a tab's tenth save of the
    afternoon from being the tenth copy of the same notice in somebody's panel.
    """
    changes: list[_audit.FieldChange] = []
    became_urgent: list[ShemaNeed] = []

    for row in plan.creates:
        need = _new_need(project.id, row, user=user, day=day)
        db.add(need)
        changes.append(_audit.FieldChange(NEEDS_FIELD_KEY, None, _lifecycle(need)))
        if _is_urgent_and_open(need):
            became_urgent.append(need)

    for need, row in plan.updates:
        was_urgent = _is_urgent_and_open(need)
        before = _lifecycle(need)
        if not _apply(need, row, user=user, day=day):
            continue
        changes.append(_audit.FieldChange(NEEDS_FIELD_KEY, before, _lifecycle(need)))
        if _is_urgent_and_open(need) and not was_urgent:
            became_urgent.append(need)

    if plan.creates:
        await db.flush()
    return changes, became_urgent


async def notify_urgent(
    db: AsyncSession,
    project: ShemaProject,
    needs: list[ShemaNeed],
    *,
    actor: User | None,
) -> int:
    """Stage **one notice per recipient for the whole batch**; answer how many were written.

    **Routed by role and then by region, before anything is capped** (FE-44 §5.10's rule for
    the panel, applied at the source): the recipients are the holders of
    :data:`URGENT_NEED_ROLES` whose scope reaches this project's region, and a holder of a role
    in another region is not a recipient rather than a recipient who is filtered out later.

    **One notice per recipient, not one per need.** A save that imports twenty needs and turns
    five of them urgent is one event, and a coordinator who received five separate notices for
    one save would learn to stop opening them — the exact failure a flood is named for in
    ``docs/shema.md``'s delivery plan. :func:`urgent_needs_notice` folds the batch into one
    ``Notice`` before anything is staged, so the recipient loop below runs once regardless of
    how many needs raised it.

    Staged inside the caller's transaction with ``commit=False``. The flag exists for exactly
    this (``create_notification``'s own docstring): a need that landed always carries its
    notice, and one that rolled back leaves none.

    **The body is built from a leaving shape**, so it cannot name the place even though the
    people it reaches could read it on the record. The notice is the payload that travels
    furthest with the least supervision — it is listed, it is counted, it is the thing a panel
    renders next to seven others — and a rule that had to be remembered here is the rule
    ``docs/shema.md`` §6.4 spends a section saying nobody remembers.
    """
    if not needs:
        return 0

    holders = await authorization_service.list_role_holders(db, SHEMA_APP_KEY, URGENT_NEED_ROLES)
    recipients = await holders_reaching(db, holders, project.region_key, SHEMA_APP_KEY)
    if not recipients:
        logger.warning(
            "shema urgent need raised and reached nobody",
            extra={
                "shema_operation": "notify_urgent",
                "shema_project_id": project.id,
                "shema_region": project.region_key.value,
                "shema_need_count": len(needs),
            },
        )
        return 0

    app_id = await get_shema_app_id(db)
    notice = urgent_needs_notice([ShemaNeedLine.of(need, project) for need in needs])
    written = 0
    for user in recipients:
        await create_notification(
            db,
            user_id=user.id,
            app_id=app_id,
            event_type=URGENT_NEED_EVENT,
            title=notice.title,
            body=notice.body,
            actor_id=None if actor is None else actor.id,
            commit=False,
        )
        written += 1
    return written


def needs_payload(payload: Any) -> list[ShemaNeedWrite] | None:
    """The batch a write payload carries, or ``None`` when it carries none.

    ``model_fields_set`` and not the value, because *absent* and *empty* are different answers
    and an empty list is a legitimate one — it simply asks for nothing, which an upsert batch
    obliges by doing nothing.
    """
    if "needs_items" not in payload.model_fields_set:
        return None
    return list(payload.needs_items or [])
