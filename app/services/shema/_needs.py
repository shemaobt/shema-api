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
from dataclasses import dataclass, field
from datetime import date
from typing import Any

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

#: The columns a batch row copies across as sent. ``id`` addresses, ``acknowledged`` is a
#: gesture the server turns into three columns, and ``submitted_at`` is the one field that can
#: be set and not cleared — :func:`raise_day_moves` says why.
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
)

#: What the trail records about a need that moved. The lifecycle and nothing else: the
#: description is free text a team wrote and could name a place, and ``_audit.py``'s own rule
#: is that a trail is read by more people and kept longer than a response body. A reader learns
#: that the need moved and goes to the record, where being allowed is checked.
_TRAIL_COLUMNS = ("category", "urgency", "status", "acknowledged_at")


def raise_day_moves(need: ShemaNeed, row: ShemaNeedWrite) -> bool:
    """Whether ``row`` states a different day from the one this need was raised on.

    ``submitted_at`` is the one field a payload can **set and cannot clear**, which is why it
    is not among :data:`_WRITTEN_COLUMNS`. Two things depend on it being answerable: the sweep
    measures a need's age from it, and FE-44 §5.8 keys a derived notification on
    ``need:{project}:{category}:{submittedAt}``. So this module stamps it at creation when the
    client sent none, and from then on a payload that carries a day moves it while a payload
    that carries ``None`` leaves it standing. *Never cleared* is not *never changed*: a
    coordinator fixing a wrong date is ordinary, and it lands.

    **Without that rule every re-save of an untouched tab is an edit.** The console sends whole
    ``NeedItem`` rows, and a field the *server* filled that the client never had would differ
    from the row on every single save: the version would bump, the trail would grow a row, and
    every other coordinator in the meeting would be refused — over a save that moved nothing.
    The record's own diff already refuses to read a re-sent value as a change; this is the same
    rule for a value the client was never given to re-send.
    """
    return row.submitted_at is not None and row.submitted_at != need.submitted_at


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

    **The same id twice in one batch is refused rather than resolved last-wins.** A client that
    sends one need twice believes two different things about it, and picking the second in
    silence is how the one it did not mean becomes the one that is stored. It would also put
    two rows in the trail for one need, the second describing a change from a state that never
    existed for anybody.

    **A row that would move nothing does not enter the plan**, so an empty plan means *this
    save changes no need* and ``save_project`` can stop at its own step 4 without bumping the
    version. That is the difference between *the tab sent its table* and *the tab changed
    something*, and only the second may refuse the other coordinators in the meeting.
    """
    existing = {
        row.id: row
        for row in (
            await db.execute(select(ShemaNeed).where(ShemaNeed.project_id == project.id))
        ).scalars()
    }

    plan, problems, seen = NeedPlan(), [], set()
    for index, row in enumerate(rows):
        if row.id is None:
            plan.creates.append(row)
        elif row.id in seen:
            problems.append(f"needsItems[{index}]: {row.id} is addressed twice in one batch")
        elif row.id in existing:
            seen.add(row.id)
            if moves(existing[row.id], row):
                plan.updates.append((existing[row.id], row))
        else:
            problems.append(f"needsItems[{index}]: {row.id} is not a need of this project")
    if problems:
        raise ValidationError("; ".join(problems))
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


def moves(need: ShemaNeed, row: ShemaNeedWrite) -> bool:
    """Whether this row would actually change this need.

    **Asked while planning and not while writing**, which is what keeps a version bump honest:
    the record's own diff decides whether a save moved anything *before* the conditional
    ``UPDATE`` runs, and a needs batch that re-sent what it read has to reach that decision the
    same way. A tab re-sending its whole table on every save is what the progress tab already
    does, and bumping the version for it would refuse every other coordinator in the meeting
    over a save that moved nothing.

    Equality and not identity, for ``_audit.py``'s reason.
    """
    if any(getattr(need, column) != getattr(row, column) for column in _WRITTEN_COLUMNS):
        return True
    if raise_day_moves(need, row):
        return True
    return row.acknowledged and need.acknowledged_at is None


def _apply(need: ShemaNeed, row: ShemaNeedWrite, *, user: User | None, day: date) -> None:
    """Move one row onto one need. :func:`moves` already said it would."""
    for column in _WRITTEN_COLUMNS:
        setattr(need, column, getattr(row, column))
    if row.submitted_at is not None:
        need.submitted_at = row.submitted_at
    if row.acknowledged:
        _acknowledge(need, user=user, day=day)


def _new_need(project_id: str, row: ShemaNeedWrite, *, user: User | None, day: date) -> ShemaNeed:
    """One need, as the batch asked for it.

    ``submitted_at`` falls back to the day the need arrived rather than staying NULL, and it is
    the one value this path supplies that the payload did not — :func:`raise_day_moves` carries
    the reason and the other half of the rule.
    """
    need = ShemaNeed(
        project_id=project_id,
        **{column: getattr(row, column) for column in _WRITTEN_COLUMNS},
    )
    need.submitted_at = row.submitted_at or day
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
        _apply(need, row, user=user, day=day)
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
    """Stage one notice per recipient per urgent need; answer how many were written.

    **Routed by role and then by region, before anything is capped** (FE-44 §5.10's rule for
    the panel, applied at the source): the recipients are the holders of
    :data:`URGENT_NEED_ROLES` whose scope reaches this project's region, and a holder of a role
    in another region is not a recipient rather than a recipient who is filtered out later.

    **The person who raised it is not told about their own act**, which is the sibling's
    ``board_watchers(exclude=...)`` and its reason: a coordinator who just typed the need does
    not need a notice saying they typed it, and the panel somebody actually reads is the one
    holding only what other people did.

    Staged inside the caller's transaction with ``commit=False``. The flag exists for exactly
    this (``create_notification``'s own docstring): a need that landed always carries its
    notice, and one that rolled back leaves none.

    **The body is written by the leaving shape itself**
    (:meth:`~app.models.shema_need.ShemaNeedLine.as_notice`), so it cannot name the place even
    though the people it reaches could read it on the record.
    A notice is the payload that travels furthest with the least supervision — it is listed, it
    is counted, it is rendered next to seven others — and a rule that had to be remembered here
    is the rule ``docs/shema.md`` §6.4 spends a section saying nobody remembers. It is also why
    the sentence is composed there and not here: this package is globbed for guarded names, and
    ``line.location`` written in this file would be a read the check cannot tell from a leak.
    """
    if not needs:
        return 0

    holders = await authorization_service.list_role_holders(db, SHEMA_APP_KEY, URGENT_NEED_ROLES)
    reaching = await holders_reaching(db, holders, project.region_key, SHEMA_APP_KEY)
    recipients = [person for person in reaching if actor is None or person.id != actor.id]
    if not recipients:
        return 0

    app_id = await get_shema_app_id(db)
    written = 0
    for need in needs:
        title, body = ShemaNeedLine.of(need, project).as_notice()
        for person in recipients:
            await create_notification(
                db,
                user_id=person.id,
                app_id=app_id,
                event_type=URGENT_NEED_EVENT,
                title=title,
                body=body,
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
