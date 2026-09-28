"""The Admin's access surface — ``/api/shema/access``, OBT-543.

Seven routes and one guard: every handler takes :data:`~app.api.shema._deps.AdminUser`, the
``admin`` role of this app (OBT-522's *Admin da plataforma*), inside the ``authenticated``
router that already refuses anybody with no role here. A Gestor or a mesa stops at that
router's gate; a coordinator, an OBT Lab, a Resource Circle or a global strategist stops at
this one. ``tests/test_shema/test_admin_gate.py`` pins the seven paths and that each carries
the guard, so an eighth route is a deliberate edit.

The handlers are what ADR 0009 asks a router to be: they declare the guard, the session and
the payload, and call one service each. The two app keys come from ``_deps.py``, where the
module names them; every rule the surface applies — the vocabulary, the mirrored ``admin``,
regions with a regional role, the self-grant — is ``app/services/shema/_grant_rules.py``'s.
``docs/shema.md`` (*The Admin grants*) is the contract the PME's screen reads: the routes, the
shapes and every refusal sentence with its status.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.shema._deps import APP_KEY, FORM_APP_KEY, AdminUser, Db
from app.models.shema_grant import (
    AccountGrants,
    GrantChange,
    InviteRequest,
    InviteWithdrawRequest,
    OpenInvite,
    RoleGrantRequest,
    RoleRevokeRequest,
    SentInvite,
)
from app.services.shema import (
    GrantApps,
    find_account,
    grant_role,
    list_grant_changes,
    list_invites,
    revoke_grant,
    send_invite,
    withdraw_invite,
)

router = APIRouter()

#: The two applications whose roles the surface grants.
APPS = GrantApps(shema=APP_KEY, form=FORM_APP_KEY)


@router.get("/access/people", response_model=AccountGrants)
async def read_account(
    actor: AdminUser, db: Db, email: str = Query(..., min_length=1)
) -> AccountGrants:
    """One account by exact e-mail: its roles in both apps, its regions, what they reach."""
    return await find_account(db, APPS, email=email)


@router.post("/access/grants", response_model=AccountGrants)
async def create_grant(payload: RoleGrantRequest, actor: AdminUser, db: Db) -> AccountGrants:
    """Grant a role — with its regions when it is regional — and answer the account."""
    return await grant_role(db, APPS, payload=payload, actor=actor)


@router.post("/access/grants/revoke", response_model=AccountGrants)
async def remove_grant(payload: RoleRevokeRequest, actor: AdminUser, db: Db) -> AccountGrants:
    """Revoke a role and answer the account."""
    return await revoke_grant(db, APPS, payload=payload, actor=actor)


@router.post("/access/invites", response_model=SentInvite, status_code=201)
async def create_invitation(payload: InviteRequest, actor: AdminUser, db: Db) -> SentInvite:
    """Invite somebody with no account; the answer carries the link, once."""
    return await send_invite(db, APPS, payload=payload, actor=actor)


@router.post("/access/invites/revoke", response_model=OpenInvite)
async def recall_invitation(payload: InviteWithdrawRequest, actor: AdminUser, db: Db) -> OpenInvite:
    """Recall an invitation nobody accepted yet."""
    return await withdraw_invite(db, APPS, invite_id=payload.invite_id, actor=actor)


@router.get("/access/invites", response_model=list[OpenInvite])
async def read_invitations(actor: AdminUser, db: Db) -> list[OpenInvite]:
    """The two apps' invitations nobody accepted, newest first."""
    return await list_invites(db, APPS)


@router.get("/access/changes", response_model=list[GrantChange])
async def read_changes(actor: AdminUser, db: Db) -> list[GrantChange]:
    """Who granted or revoked which role or region, to whom, and when — newest first."""
    return await list_grant_changes(db, APPS)
