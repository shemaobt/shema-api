"""``POST /api/shema/projects/{id}/confirm`` — the Admin confirms a project an approval filed.

OBT-547. Daniel, 25/set: *"sim, o admin confere antes"*. One act, one commit:

1. the Admin's adjustments — the language's name and code, the place, the base — and the
   sensitive-country flag, which the body must state (``ProjectConfirmation``); the region is
   derived again from the place by its one owner (``_redaction.derive_region``);
2. the project stops being pending, so every read through the scope sees it from now on;
3. every request the link sent and no project owns points at it (``_filing.stamp_link_requests``)
   — the one that filed it first among them;
4. each address on the list: an account already there joins the team (OBT-524), and an address
   with no account is invited to it (BE-22's invitation, naming the project and no role) — which
   is the membership once accepted (``apply_invited_membership``).

**The trail says who filed it.** The adjustments are written to ``shema_record_edits`` under the
Admin's name, through ``_audit`` like every other write of the record, and the place and the flag
keep their values out of it as they do there. The version stays at one: nobody could have read
the record before this, so there is no copy for the guard to protect.

**The list is the Admin's, as sent.** A blank address is left out and named back in
``withoutEmail``, so the screen can say who is not on the team yet; the same address twice is one
person; an account matched by e-mail, case aside, that is already on the team stays as it is.
The link's own address was put on the list when the project was filed, so the person who asked
is invited unless the Admin takes them off.

**Letters after the commit**, best-effort, as ``send_invite``'s: a dead provider cannot roll back a
confirmation, and each invitation's link is in the answer once for the Admin to hand over another
way when its letter did not leave.

**Refusals.** Anybody but the Admin — the route's ``AdminUser``, and the Admin's standing read
fresh here (``_grant_rules.require_admin_in``) as every write of the access surface does. An id
no approval filed is a 404; a project already confirmed or discarded is a 409 that says which.
"""

from __future__ import annotations

import logging
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, RoleError
from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_project_member import MEMBER_ROLE, ShemaProjectMember
from app.models.shema_pending import (
    ConfirmedProject,
    InvitedMember,
    JoinedMember,
    ProjectConfirmation,
)
from app.services.auth.get_user_by_email import get_user_by_email
from app.services.authorization.get_app_by_key import get_app_by_key
from app.services.common.email import send_access_invite_email
from app.services.resource_request_access.invite_store import (
    IssuedTeamInvite,
    invite_link,
    issue_team_invite,
)
from app.services.shema import _audit
from app.services.shema._filing import stamp_link_requests
from app.services.shema._grant_rules import require_admin_in
from app.services.shema._redaction import derive_region
from app.services.shema._roster import live_membership
from app.services.shema._scope import filed_projects
from app.services.shema.send_invite import INVITE_PAGE

logger = logging.getLogger(__name__)

#: The fields of the body that are columns of the record, written as the Admin sent them.
_ADJUSTED = frozenset({"language_name", "language_code", "location", "team", "sensitive_country"})


class _Invitation(NamedTuple):
    issued: IssuedTeamInvite
    url: str


async def decidable_project(db: AsyncSession, project_id: str) -> ShemaProject:
    """The project an approval filed and nobody decided yet, locked — or the refusal that fits.

    Shared with the discard: an id no approval filed is a 404 and a decided one a 409 naming
    the decision, so the two acts cannot disagree about what *already decided* means.
    """
    stmt = filed_projects().where(ShemaProject.id == project_id).with_for_update()
    project = (await db.execute(stmt)).scalar_one_or_none()
    if project is None:
        raise NotFoundError("Project not found")
    if project.discarded_at is not None:
        raise ConflictError("This project was discarded; it is not confirmed or discarded again.")
    if not project.pending_confirmation:
        raise ConflictError("This project was already confirmed.")
    return project


async def confirm_project(
    db: AsyncSession,
    project_id: str,
    *,
    payload: ProjectConfirmation,
    actor: User,
    app_key: str,
) -> ConfirmedProject:
    """Apply the Admin's conference, register the project, and seat or invite its team."""
    await require_admin_in(db, actor, (app_key,))
    landing = await get_app_by_key(db, app_key)
    if landing is None:
        raise RoleError("App not found")
    project = await decidable_project(db, project_id)

    before = _audit.snapshot(project)
    for column, value in payload.model_dump(include=set(_ADJUSTED)).items():
        setattr(project, column, value)
    project.region_key = derive_region(project)
    project.pending_confirmation = False
    project.updated_by = actor.id
    project.updated_by_name = _audit.author_name(actor)
    _audit.record_edits(
        db,
        project,
        version=project.version,
        changes=_audit.field_changes(before, project),
        user=actor,
    )

    request_ids = (
        await stamp_link_requests(db, project.source_link_id, project.id)
        if project.source_link_id
        else []
    )

    joined: list[JoinedMember] = []
    invitations: list[_Invitation] = []
    without_email: list[str] = []
    seen: set[str] = set()
    for member in payload.members:
        if not member.email:
            without_email.append(member.name)
            continue
        if member.email in seen:
            continue
        seen.add(member.email)

        account = await get_user_by_email(db, member.email)
        if account is None:
            issued = await issue_team_invite(db, actor, landing, member.email, project.id)
            url = invite_link(landing, issued.raw_token, page=INVITE_PAGE)
            invitations.append(_Invitation(issued, url))
            continue
        if await live_membership(db, project.id, account.id) is None:
            db.add(
                ShemaProjectMember(
                    project_id=project.id, user_id=account.id, role=MEMBER_ROLE, added_by=actor.id
                )
            )
        joined.append(JoinedMember(email=member.email, userId=account.id))

    confirmed_id, language_name = project.id, project.language_name
    await db.commit()

    invited = [
        InvitedMember(
            email=invitation.issued.invite.email,
            inviteId=invitation.issued.invite.id,
            inviteUrl=invitation.url,
            emailSent=await send_access_invite_email(
                to_email=invitation.issued.invite.email,
                inviter_name=actor.display_name,
                invite_url=invitation.url,
                app_name=landing.name,
            ),
        )
        for invitation in invitations
    ]

    logger.info(
        "shema pending project confirmed",
        extra={
            "shema_operation": "confirm_project",
            "shema_user_id": actor.id,
            "shema_project_id": confirmed_id,
            "shema_requests_stamped": len(request_ids),
            "shema_members_joined": len(joined),
            "shema_members_invited": len(invited),
        },
    )
    return ConfirmedProject(
        id=confirmed_id,
        languageName=language_name,
        requestIds=request_ids,
        joined=joined,
        invited=invited,
        withoutEmail=without_email,
    )
