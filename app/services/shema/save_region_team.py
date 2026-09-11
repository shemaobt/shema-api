"""The one writer of the org chart, and the reason a change is never silent.

FE-44 §5.3 and ``docs/shema.md`` §5.8 make the same demand twice: **a team change is a write
with an audit row, not a silent update.** ``shema_role_changes`` is append-only in the
database (``docs/shema.md`` §7.2 — the trigger, not a convention), so this function writing the
trail is not the guarantee; it is the only path that *can* write it, and the trail cannot be
repaired afterwards by anybody who forgets.

**Three seats are stated whole.** The screen edits a region's three fields together, so the
payload says what all three now are and a name left out is a seat emptied. That is what makes
``SaveOutcome``'s ``cleared`` a fact the server can count instead of a gesture the client has
to spell.

**The account link belongs to the holder, not to the seat.** Writing a different
``holder_name`` clears ``holder_user_id`` unless the same call supplies a new one, which is
``docs/shema.md`` §5.5's rule for a media authorization — *replacing the artifact resets the
decision to undecided* — read on a person: an account still pointing at a seat whose holder
changed is worse than an empty column, because it reads as a verified identity and nothing
about it looks stale.

**Setting only the account writes no audit row**, and that is the trail staying readable
rather than a gap in it. ``RoleChange`` is frozen as ``{from, to}`` — a *name* transition —
and a row where those two are equal says *something happened here* to a reader who then
cannot find out what. Naming the account of the person already in the seat is a correction to
a reference, stamped by ``updated_at``; it does not move anybody in or out of an office.

**The region scope is applied here and not in the router.** ``docs/shema.md`` §6.2 refuses a
scope the router applies by name. A regional ``coordinator`` writes their own region; the
refusal is :class:`~app.core.exceptions.AuthorizationError` and not a 404, because unlike a
project id the seven region keys are a public vocabulary the console already holds — there is
no existence to protect, so the honest answer is *not yours* rather than *no such thing*.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, UnknownReferenceError
from app.db.models.auth import User
from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_org_chart import ShemaRegionTeam, ShemaRoleChange
from app.models.shema_org_chart import (
    RegionTeamSave,
    RegionTeamSaved,
    RoleChange,
    SaveOutcome,
)
from app.services.shema._scope import RegionScope, reaches
from app.services.shema.list_regions import FIELD_FOR_SEAT, SEAT_ORDER
from app.utils.stored_time import as_utc

logger = logging.getLogger(__name__)


async def _account_or_refuse(db: AsyncSession, user_id: str) -> str:
    """Refuse an account that does not exist, before anything is written.

    Checked rather than left to the foreign key, for the reason
    :class:`~app.core.exceptions.UnknownReferenceError` exists at all: the database raising
    inside a flush escapes as a 500 for the caller's own bad id. The account's **grant** is
    not checked — who may sign in to Shemá is ``user_app_roles``' answer and it changes on
    its own schedule, so requiring one here would make a seat quietly wrong the day somebody's
    access was revoked for an unrelated reason.
    """
    found = await db.get(User, user_id)
    if found is None:
        raise UnknownReferenceError(f"No user with id '{user_id}'")
    return user_id


async def save_region_team(
    db: AsyncSession,
    scope: RegionScope,
    *,
    region_key: ShemaRegionKey,
    payload: RegionTeamSave,
    actor: User,
) -> RegionTeamSaved:
    """Put three names in three seats, and write the trail of whatever moved.

    ``scope`` is positional and has no default, which is ``list_projects``' rule and holds
    for its reason: a keyword with a permissive default is how a scope stops being applied,
    because the call that omits it still compiles and still passes review.
    """
    if not reaches(scope, region_key):
        logger.warning(
            "shema authorization refused: org chart write outside region scope",
            extra={
                "shema_operation": "save_region_team",
                "shema_user_id": actor.id,
                "shema_region_key": region_key.value,
                "shema_scope_global": scope.global_,
                "shema_scope_regions": sorted(scope.regions),
            },
        )
        raise AuthorizationError(f"Your scope does not include the '{region_key.value}' region.")

    accounts = payload.accounts
    for seat in SEAT_ORDER:
        wanted = getattr(accounts, FIELD_FOR_SEAT[seat]) if accounts is not None else None
        if wanted is not None:
            await _account_or_refuse(db, wanted)

    stored = {
        row.role: row
        for row in (
            await db.execute(
                select(ShemaRegionTeam).where(ShemaRegionTeam.region_key == region_key)
            )
        ).scalars()
    }

    changed_at = datetime.now(UTC)
    actor_name = actor.display_name or actor.email
    outcome = SaveOutcome()
    written: list[ShemaRoleChange] = []

    for seat in SEAT_ORDER:
        field = FIELD_FOR_SEAT[seat]
        to_name = (getattr(payload.team, field) or "").strip()
        account = getattr(accounts, field) if accounts is not None else None
        row = stored.get(seat)
        from_name = row.holder_name if row is not None else ""

        if row is None:
            row = ShemaRegionTeam(region_key=region_key, role=seat, holder_name=to_name)
            db.add(row)
        else:
            row.holder_name = to_name

        if to_name != from_name:
            row.holder_user_id = account
            outcome.changed += 1
            if not from_name:
                outcome.filled += 1
            elif not to_name:
                outcome.cleared += 1
            entry = ShemaRoleChange(
                region_key=region_key,
                role=seat,
                from_name=from_name,
                to_name=to_name,
                changed_by=actor_name,
                changed_at=changed_at,
            )
            db.add(entry)
            written.append(entry)
        elif account is not None:
            row.holder_user_id = account

    await db.commit()

    return RegionTeamSaved(
        outcome=outcome,
        changes=[
            RoleChange.model_validate(
                {
                    "regionKey": entry.region_key.value,
                    "role": entry.role.value,
                    "from": entry.from_name,
                    "to": entry.to_name,
                    "changedBy": entry.changed_by,
                    "changedAt": as_utc(entry.changed_at).date(),
                }
            )
            for entry in written
        ],
    )
