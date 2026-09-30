"""The invitation's rows, behind no gate: the one reader and writer of ``access_invites``.

Every door that invites applies its own gate first and then comes here. Since FE-56 (OBT-549,
30/sep/2026) that is the Shemá Admin's surface alone (OBT-543, ``docs/shema.md``, *The Admin
grants*): the form's own doors — ``create_invite``, ``revoke_invite``, ``list_access`` and
their asymmetric gate — left with its access screen. What this file holds is everything that is
not a question of who may: the token and its digest, the refusal of a second pending invite, the
self-invite, the link, the states.

**It stayed where it is, and so did ``accept_invite`` and ``describe_invite``** (option A,
decided on 30/sep): the PME's ``/convite`` page still reads and accepts an invite through the
form's two public routes, and the Shemá module imports this store. Moving the three into that
module with their routes is a follow-up; deleting them would take the PME's invitations with
them.

Acceptance is not here: ``accept_invite`` is its own operation, with its own transaction.

**An invitation to a project's team carries no role** (OBT-547). Confirming a project the mesa's
approval filed invites each proposed member with no account, and what accepting gives is a
membership (OBT-524), not a grant — so the row names the project and no role, and it is read
everywhere else as :data:`TEAM_ROLE`, the word the PME's session answers for a membership. It is
written inside the confirmation's transaction, which is why :func:`issue_team_invite` flushes and
does not commit: the project, the memberships and the invitations are one act.
"""

import secrets
from collections.abc import Collection, Sequence
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, RoleError
from app.db.models.auth import AccessInvite, App, Role, User
from app.db.models.shema_project_member import MEMBER_ROLE
from app.services.auth.hash_refresh_token import hash_refresh_token
from app.services.authorization.get_app_by_key import get_app_by_key
from app.services.authorization.get_role import get_role

#: Where a link lands when the app row names no URL — a development console. One place, so the
#: two doors cannot disagree about it.
FALLBACK_APP_URL = "http://localhost:5173"

#: How an invitation to a project's team reads where a role would: it grants none, and the
#: membership it gives is what the PME's session calls ``equipe``.
TEAM_ROLE = MEMBER_ROLE


class IssuedInvite(NamedTuple):
    """A new invite, its app and role, and the raw token — which leaves this module once."""

    invite: AccessInvite
    app: App
    role: Role
    raw_token: str


class InviteRow(NamedTuple):
    """An invite read back, with the two keys every caller renders it by."""

    invite: AccessInvite
    app_key: str
    role_key: str


class IssuedTeamInvite(NamedTuple):
    """A new invitation to a project's team and its raw token, which leaves this module once."""

    invite: AccessInvite
    raw_token: str


async def issue_invite(
    db: AsyncSession,
    actor: User,
    app_key: str,
    email: str,
    role_key: str,
    *,
    region_keys: Sequence[str] | None = None,
) -> IssuedInvite:
    """Write a single-use invite and hand back its raw token; only the SHA-256 is stored.

    Inviting your own e-mail is refused as the self-grant it would become, and a second
    pending invite for the same e-mail, app and role as a duplicate. The row is committed
    here, before any letter leaves, so a dead provider cannot roll it back.
    """
    normalized_email = email.strip().lower()
    if normalized_email == actor.email.lower():
        raise RoleError("You cannot invite yourself.")

    app = await get_app_by_key(db, app_key)
    if not app:
        raise RoleError("App not found")

    role = await get_role(db, app.id, role_key)
    if not role:
        raise RoleError("Role not found")

    now = datetime.now(UTC)
    stmt = select(AccessInvite.id).where(
        AccessInvite.app_id == app.id,
        AccessInvite.role_id == role.id,
        AccessInvite.email == normalized_email,
        AccessInvite.accepted_at.is_(None),
        AccessInvite.revoked_at.is_(None),
        AccessInvite.expires_at > now,
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        raise ConflictError("An invitation for this e-mail and role is already pending.")

    raw_token = secrets.token_hex(32)
    invite = AccessInvite(
        app_id=app.id,
        role_id=role.id,
        email=normalized_email,
        token_hash=hash_refresh_token(raw_token),
        expires_at=now + timedelta(days=get_settings().access_invite_expire_days),
        region_keys=list(region_keys) if region_keys else None,
        created_by=actor.id,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return IssuedInvite(invite=invite, app=app, role=role, raw_token=raw_token)


async def issue_team_invite(
    db: AsyncSession, actor: User, app: App, email: str, project_id: str
) -> IssuedTeamInvite:
    """Stage a single-use invitation to ``project_id``'s team, in the caller's transaction.

    No role, and no refusal of a second pending one: the caller writes one per address of a list
    it has already made unique, for a project nobody could invite to before.
    """
    raw_token = secrets.token_hex(32)
    invite = AccessInvite(
        app_id=app.id,
        role_id=None,
        project_id=project_id,
        email=email.strip().lower(),
        token_hash=hash_refresh_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(days=get_settings().access_invite_expire_days),
        created_by=actor.id,
    )
    db.add(invite)
    await db.flush()
    return IssuedTeamInvite(invite=invite, raw_token=raw_token)


def invite_link(app: App, raw_token: str, *, page: str = "invite") -> str:
    """The link a letter carries: the landing app's own URL, its invitation page, the token."""
    base_url = app.app_url.rstrip("/") if app.app_url else FALLBACK_APP_URL
    return f"{base_url}/{page}?token={raw_token}"


def _rows() -> Select[tuple[AccessInvite, str, str]]:
    return (
        select(AccessInvite, App.app_key, Role.role_key)
        .join(App, App.id == AccessInvite.app_id)
        .outerjoin(Role, Role.id == AccessInvite.role_id)
    )


def _row(invite: AccessInvite, app_key: str, role_key: str | None) -> InviteRow:
    return InviteRow(invite, app_key, role_key or TEAM_ROLE)


async def find_invite(
    db: AsyncSession, invite_id: str, *, app_keys: Collection[str] | None = None
) -> InviteRow:
    """One invite by id — ``NotFoundError`` when there is none, or it belongs to another app.

    ``app_keys`` narrows the answer to the apps a door serves. An invite outside them reads
    exactly as a missing one, so a door cannot be used to learn that some other app's invite
    exists.
    """
    stmt = _rows().where(AccessInvite.id == invite_id)
    if app_keys is not None:
        stmt = stmt.where(App.app_key.in_(list(app_keys)))
    found = (await db.execute(stmt)).one_or_none()
    if found is None:
        raise NotFoundError("Invitation not found.")
    invite, app_key, role_key = found
    return _row(invite, app_key, role_key)


async def find_invites(
    db: AsyncSession,
    app_keys: Collection[str],
    *,
    newest_first: bool = False,
    limit: int | None = None,
) -> list[InviteRow]:
    """The invites of ``app_keys`` nobody accepted yet — pending, expired and revoked alike.

    Accepted ones are left out because they became grants and are read as such; revoked and
    expired ones stay, so a recalled or lapsed door is visible rather than silently gone.
    """
    stmt = _rows().where(App.app_key.in_(list(app_keys)), AccessInvite.accepted_at.is_(None))
    order = AccessInvite.created_at.desc() if newest_first else AccessInvite.created_at
    stmt = stmt.order_by(order, AccessInvite.id)
    if limit is not None:
        stmt = stmt.limit(limit)
    return [_row(invite, app_key, role_key) for invite, app_key, role_key in await db.execute(stmt)]


async def recall_invite(db: AsyncSession, actor: User, invite: AccessInvite) -> AccessInvite:
    """Close a not-yet-accepted invite; idempotent on repeat.

    An *accepted* invite is past recalling — the grant it produced is the thing to revoke.
    """
    if invite.accepted_at is not None:
        raise ConflictError(
            "This invitation was already accepted; revoke the granted role instead."
        )
    if invite.revoked_at is None:
        invite.revoked_at = datetime.now(UTC)
        invite.revoked_by = actor.id
        await db.commit()
        await db.refresh(invite)
    return invite


async def recall_pending_invites(
    db: AsyncSession, actor: User, *, email: str, app_key: str, role_key: str
) -> None:
    """Close every live invite for this e-mail, app and role, inside the caller's transaction.

    A grant or a revocation written directly supersedes an invite for the same thing: left
    open, a week-old link would hand back a role that was just revoked, or restate regions an
    Admin has since changed. Flushes and does not commit.
    """
    app = await get_app_by_key(db, app_key)
    if not app:
        return
    role = await get_role(db, app.id, role_key)
    if not role:
        return
    await db.execute(
        update(AccessInvite)
        .where(
            AccessInvite.app_id == app.id,
            AccessInvite.role_id == role.id,
            AccessInvite.email == email.strip().lower(),
            AccessInvite.accepted_at.is_(None),
            AccessInvite.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC), revoked_by=actor.id)
    )
    await db.flush()
